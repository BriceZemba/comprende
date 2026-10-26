"""The explainer: a second agent that writes one specific reason per pick, in English, French and Spanish.

The planner (agent.py) decides which Qloo calls to make; the ranker decides what the learner sees. The
explainer only puts that decision into words. It is given Qloo's own description of each title (genre,
themes, emotional tone, typed tags) and the favourite Qloo credits for the match, and is told to use
nothing else: no invented plot points, no difficulty claims (those come from the subtitles and are shown
as numbers). Its output is checked; anything missing or malformed keeps the card's standard text.
"""
import asyncio
import json
import re

from . import config, openrouter, quota

LANGS = ("en", "fr", "es")
# The lite model writes these well enough and is the fastest; the larger one is the backup. Titles are
# explained in small groups written in parallel: one call for 13 titles in 3 languages took 8-20 s.
MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
GROUP = 7  # 2 requests for a usual 13 picks: the free tier counts requests, not tokens
# Reasons already written, by (title, credited favourite): re-running the same example costs no model call
# while the server stays warm. Bounded so it cannot grow without limit.
_CACHE: dict[tuple, dict] = {}
_CACHE_MAX = 3000
MAX_CHARS = 200
TIMEOUT_S = 10.0
# Typed Qloo tags worth naming. "keyword" tags are left out: they are noisy ("Telephone call") and
# sometimes inappropriate for a card.
TAG_TYPES = ("genre", "subgenre", "theme", "plot", "audience", "interests")

SYSTEM = """You write the one-line reason under each film or series recommended to a Spanish learner.
For every item you get Qloo's description of the title (genre, themes, emotional tone, tags) and the
learner's favourites, with the one Qloo credits for this match when there is one.
Write ONE sentence per item, at most 22 words, saying what the title is like and why it suits this learner.
- Use only the facts given for that item. Do not invent plot details, actors, awards or places.
- If a credited favourite is given, connect the title to it through a shared quality (tone, theme, mood).
  Favourites may be games, singers or books: then link through mood or theme ("the same eerie, quest-like
  atmosphere"), never "like <favourite>" as if it were a film. Write the favourite's name exactly as given.
- If several favourites are credited, the title fits them together: link it through what they share
  (for a heist series and a crime drama: tension, crime, moral greys), without singling one out.
- If no favourite is credited, connect the title to the learner's taste as a whole, without naming one.
- Never mention vocabulary, difficulty, percentages, Spanish level or the word "Qloo".
- Do not start with the title. No quotation marks, no emoji.
Return the same sentence in English (en), French (fr) and Spanish (es); natural, not word-for-word.
In Spanish use "tú"; in French use "vous", with correct elision (d'escroquerie, l'aventure). Keep titles as given."""


def tag_names(tags: list[dict]) -> list[str]:
    """Names of the typed Qloo tags worth showing, in Qloo's order, without duplicates."""
    out: list[str] = []
    for t in tags:
        kind = (t.get("id") or "").split(":")
        if len(kind) > 2 and kind[2] in TAG_TYPES and t.get("name") and t["name"] not in out:
            out.append(t["name"])
    return out[:8]


def facts(picks: list[dict], candidates: dict[str, object], favourites: list[str]) -> list[dict]:
    """One compact fact sheet per pick. Picks without any Qloo description are skipped."""
    out = []
    for p in picks:
        c = candidates.get(p.get("qloo_id") or "")
        traits = getattr(c, "traits", {}) or {}
        tags = getattr(c, "tags", []) or []
        if not traits and not tags:
            continue
        out.append({
            "key": pick_key(p), "title": p["name"], "kind": p["kind"], "year": p.get("year"),
            "credited_favourite": ", ".join(p.get("because") or []) or None,
            "genre": traits.get("genre"), "themes": traits.get("plot_themes"), "tone": traits.get("emotional_tone"),
            "tags": tags,
        })
    return out


def pick_key(p: dict) -> str:
    """Same key as the web app's pickKey: Qloo id, else IMDb id, else name."""
    return p.get("qloo_id") or p.get("imdb") or p["name"]


def validate(raw: object, wanted: set[str]) -> dict[str, dict[str, str]]:
    """Keep only well-formed entries for known keys: three non-empty, short, single-line sentences."""
    good: dict[str, dict[str, str]] = {}
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or item.get("key") not in wanted:
            continue
        texts = {lang: re.sub(r"\s+", " ", str(item.get(lang) or "").replace("_", " ")).strip().strip('"“”«»')
                 for lang in LANGS}
        if all(0 < len(t) <= MAX_CHARS for t in texts.values()) and not any(
                re.search(r"\d+\s?%|qloo", t, re.IGNORECASE) for t in texts.values()):
            good[item["key"]] = texts
    return good


async def explain(picks: list[dict], candidates: dict[str, object], favourites: list[str]) -> dict:
    """{pick key: {"en": ..., "fr": ..., "es": ...}} for the picks the model explained well; {} on any failure."""
    sheet = facts(picks, candidates, favourites)
    if not sheet or not (config.GEMINI_API_KEY or config.OPENROUTER_API_KEY):
        return {}
    from google import genai

    def cache_key(f: dict) -> tuple:
        return f["key"], f["credited_favourite"]

    out = {f["key"]: _CACHE[cache_key(f)] for f in sheet if cache_key(f) in _CACHE}
    todo = [f for f in sheet if f["key"] not in out]
    if not todo:
        return out
    client = genai.Client(api_key=config.GEMINI_API_KEY) if config.GEMINI_API_KEY else None
    groups = [todo[i:i + GROUP] for i in range(0, len(todo), GROUP)]
    for part in await asyncio.gather(*(_explain_group(client, g, favourites) for g in groups)):
        out.update(part)
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.clear()
    for f in todo:
        if f["key"] in out:
            _CACHE[cache_key(f)] = out[f["key"]]
    return out


async def _explain_group(client, sheet: list[dict], favourites: list[str]) -> dict:
    from google.genai import types

    schema = types.Schema(type=types.Type.ARRAY, items=types.Schema(
        type=types.Type.OBJECT, required=["key", *LANGS],
        properties={"key": types.Schema(type=types.Type.STRING),
                    **{lang: types.Schema(type=types.Type.STRING) for lang in LANGS}}))
    prompt = json.dumps({"favourites": favourites, "items": sheet}, ensure_ascii=False)
    for model in MODELS if config.GEMINI_API_KEY else []:
        if not quota.available(model):
            continue
        level = config.GEMINI_THINKING.get(model)
        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM, temperature=0.4, response_mime_type="application/json",
            response_schema=schema,
            **({"thinking_config": types.ThinkingConfig(thinking_level=level)} if level else {}))
        try:
            resp = await asyncio.wait_for(
                client.aio.models.generate_content(model=model, contents=prompt, config=cfg), timeout=TIMEOUT_S)
            return validate(json.loads(resp.text or "[]"), {f["key"] for f in sheet})
        except Exception as e:  # slow, busy, out of quota or malformed: try the next model
            quota.note_error(model, e)
            continue
    return await _explain_group_openrouter(sheet, prompt)


async def _explain_group_openrouter(sheet: list[dict], prompt: str) -> dict:
    """Backup when both Gemini models fail: an open model through OpenRouter, asked for the same JSON."""
    if not config.OPENROUTER_API_KEY:
        return {}
    ask = (prompt + '\nAnswer with JSON only: {"items": [{"key": ..., "en": ..., "fr": ..., "es": ...}, ...]}')
    for model in config.OPENROUTER_MODELS:
        if not quota.available(model):
            continue
        try:
            msg = await openrouter.chat(model, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": ask}],
                                        json_mode=True, timeout=25)
            data = json.loads(msg.get("content") or "{}")
            return validate(data.get("items") if isinstance(data, dict) else data, {f["key"] for f in sheet})
        except Exception as e:
            quota.note_error(model, e)
            continue
    return {}
