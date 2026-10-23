"""The Comprende agent.

Gemini plans and calls tools; Qloo supplies taste, the subtitle pipeline supplies
comprehension, and the deterministic ranker decides the order. The model writes the
words a learner reads (why each pick fits), never the numbers.

If Gemini is unavailable the same tools run in a fixed order, so the app keeps working.
"""
import asyncio
import json
import os
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from . import config
from .catalog import Catalog
from .qloo import Entity, QlooClient, QlooError
from .ranker import Candidate, rank

SPANISH_RELEASE_COUNTRIES = ["Spain", "Mexico", "Argentina", "Colombia", "Chile", "Peru", "Uruguay",
                             "Venezuela", "Cuba", "Ecuador", "Bolivia", "Paraguay", "Guatemala",
                             "Dominican Republic", "Puerto Rico", "Costa Rica", "Panama"]
KINDS = {"movie": "urn:entity:movie", "tv_show": "urn:entity:tv_show", "artist": "urn:entity:artist",
         "book": "urn:entity:book", "videogame": "urn:entity:videogame", "podcast": "urn:entity:podcast",
         "brand": "urn:entity:brand", "person": "urn:entity:person"}
# Genre tags that mark Spanish-language or Latin music and podcasts. Qloo has no language field for
# artists or podcasts, so the lane relies on tags found at run time; with no match it stays empty.
AUDIO_TAG_QUERIES = {
    "artist": ["latin", "reggaeton", "spanish", "flamenco", "salsa", "cumbia", "bachata", "en español",
               "regional mexican", "rock en espanol"],
    # Podcasts: Qloo's "Spanish" podcast tags are topics (Spanish history, Spanish civil war), not the
    # language of the show, so podcasts are left out rather than risk English shows about Spain.
    "podcast": [],
}
# Instrumental genres do not help listening practice.
INSTRUMENTAL_WORDS = ("guitar", "jazz", "house", "chill", "instrumental")
AUDIO_TAG_TYPES = {"artist": ["urn:tag:genre:music"], "podcast": ["urn:tag:genre:media"]}
# Qloo puts the broad tags "Latin" and "Spanish" on French acts too (Kendji Girac, Kouz-1, Revolver), so an
# artist must also carry a genre that is sung in Spanish, and no genre that is sung in another language.
SPANISH_GENRES = re.compile(r"reggaeton|cumbia|salsa|bachata|flamenco|merengue|bolero|ranchera|corrido|mariachi|"
                            r"tango|vallenato|dembow|trap latino|urbano latino|latin (pop|rap|rock|trap|urban|"
                            r"alternative|hip hop|ballad)|spanish (pop|rap|rock|hip hop|indie|punk|metal)|"
                            r"en espa[nñ]ol|regional mexican|folklore argentino|cantautor", re.IGNORECASE)
OTHER_LANGUAGE_GENRES = re.compile(r"french (pop|rap|hip hop|chanson|rock|variety)|chanson|vari[eé]t[eé]|"
                                   r"french caribbean|zouk|brazilian|mpb|sertanejo|bossa nova|samba|portuguese|"
                                   r"fado|italian|k-pop|j-pop|german|"
                                   r"downtempo|trip hop|lounge|chillout|instrumental", re.IGNORECASE)  # little singing
MAX_TURNS = 10
MAX_SCORED_PER_TYPE = 400
# Latency budget for the model: per call, and for the whole planning phase. Past it, the run
# finishes with the fixed plan from wherever the model got to.
MODEL_CALL_TIMEOUT_S = float(os.environ.get("MODEL_CALL_TIMEOUT_S", "12"))
MODEL_BUDGET_S = float(os.environ.get("MODEL_BUDGET_S", "25"))

Emit = Callable[[dict], Awaitable[None]]

SYSTEM = """You are Comprende, an agent that helps people learning Spanish find films and series
they will both love and understand.

Process:
1. Resolve every favourite the learner mentions into a Qloo entity with find_entity. Favourites can be
   from any domain: shows, films, music artists, books, games, podcasts, brands. If several matches fit,
   choose the most likely one and say which you chose.
2. Call recommend_spanish_titles for films and for series using all resolved favourites.
3. Call score_measured_titles for films and for series, so titles whose difficulty we measured are scored
   against the learner's taste too.
4. Call recommend_spanish_audio for artists (listening practice).
5. Call rank_for_learner, then answer.

Rules: only mention titles returned by the tools. Never state a number that a tool did not return.
Comprehension figures come from real subtitle text; affinity comes from Qloo's taste graph."""

TOOLS = [
    {
        "name": "find_entity",
        "description": "Search Qloo's taste graph for an entity the learner likes. Returns up to 5 matches.",
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Name as the learner wrote it"},
                "kind": {"type": "string", "enum": list(KINDS), "description": "Best guess of the domain"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "recommend_spanish_titles",
        "description": "Qloo recommendations of films or series originally released in Spanish-speaking "
                       "countries, driven by the learner's favourites (cross-domain).",
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "signal_entity_ids": {"type": "array", "items": {"type": "string"}},
                "kind": {"type": "string", "enum": ["movie", "tv_show"]},
            },
            "required": ["signal_entity_ids", "kind"],
        },
    },
    {
        "name": "score_measured_titles",
        "description": "Score the Spanish titles whose dialogue difficulty we measured against the "
                       "learner's favourites, using Qloo affinity.",
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "signal_entity_ids": {"type": "array", "items": {"type": "string"}},
                "kind": {"type": "string", "enum": ["movie", "tv_show"]},
            },
            "required": ["signal_entity_ids", "kind"],
        },
    },
    {
        "name": "recommend_spanish_audio",
        "description": "Qloo recommendations of Spanish-language or Latin music artists that fit the learner's "
                       "favourites. For listening practice; difficulty is not measured for these.",
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "signal_entity_ids": {"type": "array", "items": {"type": "string"}},
                "kind": {"type": "string", "enum": ["artist"]},
            },
            "required": ["signal_entity_ids", "kind"],
        },
    },
    {
        "name": "rank_for_learner",
        "description": "Rank all candidates by how much of the dialogue the learner can follow, then by taste.",
        "parameters_json_schema": {"type": "object", "properties": {}},
    },
]


_AUDIO_TAG_CACHE: dict[str, list[dict]] = {}


def _because(e: Entity, favourites: dict[str, str]) -> list[str]:
    """The favourites Qloo says drove this pick, but only when they clearly stand out.

    Qloo's explainability scores sum to about 1 across the signals. With three favourites they are
    usually near 0.33 each, and naming the "top two" would be noise ("because you like Zelda" on a
    prison drama). A favourite is named only if its share is well above an even split; an empty
    list means the pick comes from all favourites together."""
    scored = sorted(((x.get("score") or 0, favourites[x["entity_id"]]) for x in e.explainability
                     if x.get("entity_id") in favourites), reverse=True)
    if len(scored) == 1:
        return [scored[0][1]] if scored[0][1] else []
    even = 1 / max(1, len(scored))
    return [name for score, name in scored[:2] if name and score >= max(0.42, 1.3 * even)]


def sings_spanish(tag_names: list[str]) -> bool:
    """True when an artist's Qloo genres say Spanish-language music (see SPANISH_GENRES)."""
    return (any(SPANISH_GENRES.search(n) for n in tag_names)
            and not any(OTHER_LANGUAGE_GENRES.search(n) for n in tag_names))


def _imdb_ids(e: Entity) -> list[str]:
    return [x.get("id") for x in (e.external.get("imdb") or []) if isinstance(x, dict) and x.get("id")]


@dataclass
class Session:
    vocab_size: int
    favourites: dict[str, str] = field(default_factory=dict)  # qloo id -> name
    candidates: list[Candidate] = field(default_factory=list)
    excluded: set[str] = field(default_factory=set)
    listen: list[dict] = field(default_factory=list)
    result: dict | None = None
    done: set[tuple[str, str]] = field(default_factory=set)  # (tool, kind) calls that completed


class ComprendeAgent:
    def __init__(self, qloo: QlooClient, catalog: Catalog, emit: Emit):
        self.qloo, self.catalog, self.emit = qloo, catalog, emit
        self.model_used: str | None = None
        self.deadline = float("inf")
        self.qloo_errors: list[str] = []

    # ---- tools ---------------------------------------------------------------

    async def find_entity(self, s: Session, query: str, kind: str | None = None) -> dict:
        await self.emit({"type": "step", "tool": "find_entity", "text": f"Looking up “{query}” in Qloo",
                         "data": {"query": query}})
        types = [KINDS[kind]] if kind in KINDS else None
        rows = await self.qloo.search(query, types, take=5)
        if not rows and types:
            rows = await self.qloo.search(query, None, take=5)
        if rows:
            s.favourites.setdefault(rows[0].entity_id, rows[0].name)
        return {"matches": [{"id": r.entity_id, "name": r.name, "kind": r.subtype.rsplit(":", 1)[-1], "year": r.year}
                            for r in rows]}

    async def recommend_spanish_titles(self, s: Session, signal_entity_ids: list[str], kind: str) -> dict:
        label = "films" if kind == "movie" else "series"
        await self.emit({"type": "step", "tool": "recommend_spanish_titles",
                         "text": f"Asking Qloo for Spanish-language {label} that match your taste",
                         "data": {"kind": kind}})
        self._remember(s, signal_entity_ids)
        rows = await self.qloo.insights(**{
            "filter.type": KINDS[kind], "signal.interests.entities": signal_entity_ids,
            "filter.release_country": SPANISH_RELEASE_COUNTRIES, "operator.filter.release_country": "union",
            "feature.explainability": True, "take": 40,
        })
        spanish = [r for r in rows if self.catalog.match(r.entity_id, _imdb_ids(r))
                   or self.catalog.is_spanish_original(_imdb_ids(r), r.countries)]
        added = self._add(s, spanish, kind)
        measured = sum(1 for c in added if c.measured)
        return {"returned": len(rows), "dropped_not_spanish_original": len(rows) - len(spanish),
                "with_measured_difficulty": measured, "top": [c.name for c in added[:8]]}

    async def score_measured_titles(self, s: Session, signal_entity_ids: list[str], kind: str) -> dict:
        label = "films" if kind == "movie" else "series"
        want = "film" if kind == "movie" else "series"
        # The best-known measured titles (catalog order), capped to keep a run within ~8 Qloo calls per type.
        ids = [t.qloo_id for t in self.catalog.titles if t.qloo_id and t.kind == want][:MAX_SCORED_PER_TYPE]
        if not ids:
            return {"scored": 0, "top": [], "note": f"no measured {label} are mapped to Qloo yet"}
        await self.emit({"type": "step", "tool": "score_measured_titles",
                         "text": f"Scoring {len(ids)} {label} with measured dialogue against your taste",
                         "data": {"kind": kind, "count": len(ids)}})
        self._remember(s, signal_entity_ids)
        rows: list[Entity] = []
        for i in range(0, len(ids), 50):
            rows += await self.qloo.insights(**{
                "filter.type": KINDS[kind], "signal.interests.entities": signal_entity_ids,
                "filter.results.entities": ids[i:i + 50], "feature.explainability": True, "take": 50,
            })
        added = self._add(s, rows, kind)
        return {"scored": len(rows), "top": [c.name for c in sorted(added, key=lambda c: -(c.affinity or 0))[:8]]}

    async def recommend_spanish_audio(self, s: Session, signal_entity_ids: list[str], kind: str = "artist") -> dict:
        if not AUDIO_TAG_QUERIES.get(kind):
            return {"returned": 0, "note": f"{kind} recommendations are not available"}
        label = "music" if kind == "artist" else "podcasts"
        await self.emit({"type": "step", "tool": "recommend_spanish_audio",
                         "text": f"Asking Qloo for Spanish-language {label} that {'matches' if kind == 'artist' else 'match'} your taste",
                         "data": {"kind": kind}})
        self._remember(s, signal_entity_ids)
        tags = await self._audio_tags(kind)
        if not tags:
            return {"returned": 0, "note": f"no Spanish or Latin tags found for {label}"}
        rows = await self.qloo.insights(**{
            "filter.type": f"urn:entity:{kind}", "signal.interests.entities": signal_entity_ids,
            "filter.tags": [t["id"] for t in tags], "operator.filter.tags": "union",
            "feature.explainability": True, "take": 30,
        })
        returned = len(rows)
        if kind == "artist":
            rows = [r for r in rows if sings_spanish([t.get("name") or "" for t in r.tags])]
        tag_names = {t["id"]: t["name"] for t in tags}
        seen = {x["qloo_id"] for x in s.listen}
        for r in rows:
            if r.entity_id in seen or r.entity_id in s.excluded or r.entity_id in s.favourites                     or r.name.lower() in {n.lower() for n in s.favourites.values()}:
                continue  # never hand a favourite back as a recommendation
            because = _because(r, s.favourites)
            s.listen.append({"qloo_id": r.entity_id, "name": r.name, "kind": kind, "image": r.image,
                             "description": r.description, "affinity": r.affinity, "because": [b for b in because if b],
                             "spanish_tags": [tag_names[t["id"]] for t in r.tags if t.get("id") in tag_names]})
        return {"returned": returned, "sung_in_spanish": len(rows), "top": [r.name for r in rows[:6]]}

    async def _audio_tags(self, kind: str) -> list[dict]:
        if kind in _AUDIO_TAG_CACHE:
            return _AUDIO_TAG_CACHE[kind]
        found: dict[str, dict] = {}
        for q in AUDIO_TAG_QUERIES[kind]:
            for t in await self.qloo.tags(q, AUDIO_TAG_TYPES[kind], take=10):
                words = q.replace("ñ", "n").split()
                name = t["name"].lower().replace("ñ", "n")
                if all(w.replace("ñ", "n") in name for w in words) and not any(x in name for x in INSTRUMENTAL_WORDS):
                    found[t["id"]] = t
        _AUDIO_TAG_CACHE[kind] = list(found.values())
        return _AUDIO_TAG_CACHE[kind]

    async def rank_for_learner(self, s: Session) -> dict:
        await self.emit({"type": "step", "tool": "rank_for_learner",
                         "text": f"Checking each title's dialogue against your ~{s.vocab_size:,} words",
                         "data": {"vocab": s.vocab_size}})
        s.result = rank([c for c in s.candidates if (c.qloo_id or "") not in s.excluded], s.vocab_size)
        b = s.result["buckets"]
        return {
            "watch_now": [p["name"] for p in b["watch_now"]],
            "stretch": [p["name"] for p in b["stretch"]],
            "held_back": s.result["held_back"]["name"] if s.result["held_back"] else None,
            "unmeasured": [p["name"] for p in b["unmeasured"]],
        }

    # ---- helpers -------------------------------------------------------------

    def _remember(self, s: Session, ids: list[str]) -> None:
        for i in ids:
            s.favourites.setdefault(i, i)

    def _add(self, s: Session, rows: list[Entity], kind: str) -> list[Candidate]:
        out = []
        for r in rows:
            imdb = _imdb_ids(r)
            because = _because(r, s.favourites)
            c = Candidate(qloo_id=r.entity_id, name=self.catalog.spanish_name(imdb) or r.name,
                          kind="film" if kind == "movie" else "series",
                          year=r.year, image=r.image, description=r.description, affinity=r.affinity,
                          popularity=r.popularity, because=[b for b in because if b],
                          measured=self.catalog.match(r.entity_id, imdb))
            s.candidates.append(c)
            out.append(c)
        return out

    async def _call(self, s: Session, name: str, args: dict) -> dict:
        fn = {"find_entity": self.find_entity, "recommend_spanish_titles": self.recommend_spanish_titles,
              "score_measured_titles": self.score_measured_titles,
              "recommend_spanish_audio": self.recommend_spanish_audio, "rank_for_learner": self.rank_for_learner}.get(name)
        if not fn:
            return {"error": f"unknown tool {name}"}
        try:
            out = await fn(s, **args)
            s.done.add((name, str(args.get("kind", ""))))
            return out
        except QlooError as e:
            self.qloo_errors.append(e.code)
            await self.emit({"type": "warning", "code": "qloo", "data": {"code": e.code},
                             "text": f"Qloo did not answer ({e.code})"})
            return {"error": e.code, "retryable": e.retryable}

    # ---- runs ----------------------------------------------------------------

    async def run(self, favourites_text: str, favourite_ids: dict[str, str], vocab_size: int,
                  exclude_ids: list[str] | None = None) -> dict:
        s = Session(vocab_size=vocab_size, favourites=dict(favourite_ids), excluded=set(exclude_ids or []))
        # The client is shared by all runs in this process; count only this run's requests.
        requests_before = self.qloo.calls + self.qloo.cached
        mode = "agent"
        if config.GEMINI_API_KEY:
            try:
                await self._run_llm(s, favourites_text)
            except Exception as e:  # outage, quota or too slow: fall back, never leave the learner with nothing
                why = ("is slow right now" if isinstance(e, TimeoutError)
                       else f"is unavailable ({type(e).__name__})")
                await self.emit({"type": "warning", "code": "fallback", "data": {"slow": isinstance(e, TimeoutError)},
                                 "text": f"The language model {why}; finishing with the fixed plan"})
                mode = "fallback"
                await self._run_fixed(s, favourites_text)
        else:
            mode = "fallback"
            await self._run_fixed(s, favourites_text)
        if s.result is None:
            await self.rank_for_learner(s)
        listen = sorted(s.listen, key=lambda x: -(x["affinity"] or 0))
        return {"mode": mode, "model": self.model_used, "favourites": s.favourites,
                "qloo_calls": self.qloo.calls + self.qloo.cached - requests_before,
                "qloo_errors": sorted(set(self.qloo_errors)), "qloo_unavailable": bool(self.qloo_errors) and not s.candidates,
                "listen": {"artists": [x for x in listen if x["kind"] == "artist"][:8],
                           "podcasts": [x for x in listen if x["kind"] == "podcast"][:6]},
                **s.result}

    async def _run_fixed(self, s: Session, favourites_text: str) -> None:
        # Reuse favourites already resolved (picked in the app, or by the model before it stopped);
        # look up only the typed ones not found yet.
        parts = favourites_text.replace(";", ",").replace(" and ", ",").replace(" y ", ",").split(",")
        known = {n.lower() for n in s.favourites.values()}
        for name in [x.strip() for x in parts if x.strip()]:
            if not any(name.lower() in k or k in name.lower() for k in known):
                await self._call(s, "find_entity", {"query": name})
        # Keep what the model already finished (the ranker drops duplicates) and run only the missing calls,
        # so a model that times out at the last step does not double the run time and the Qloo calls.
        ids = list(s.favourites)[:10]
        plan = [("recommend_spanish_titles", "movie"), ("score_measured_titles", "movie"),
                ("recommend_spanish_titles", "tv_show"), ("score_measured_titles", "tv_show"),
                ("recommend_spanish_audio", "artist")]
        for tool, kind in plan:
            if (tool, kind) not in s.done:
                await self._call(s, tool, {"signal_entity_ids": ids, "kind": kind})
        await self._call(s, "rank_for_learner", {})

    async def _generate(self, client, models: list[str], contents, cfg):
        """Call the first available model; drop overloaded or rate-limited ones for the rest of the run."""
        from google.genai import errors

        while models:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("model budget spent")
            try:
                resp = await asyncio.wait_for(
                    client.aio.models.generate_content(model=models[0], contents=contents, config=cfg),
                    timeout=min(MODEL_CALL_TIMEOUT_S, remaining))
                self.model_used = models[0]
                return resp
            except asyncio.TimeoutError:
                if len(models) > 1 and self.deadline - time.monotonic() > 3:
                    await self.emit({"type": "warning", "code": "model_slow", "data": {"from": models[0], "to": models[1]},
                                      "text": f"{models[0]} is slow, switching to {models[1]}"})
                    models.pop(0)
                    continue
                raise TimeoutError("model too slow") from None
            except errors.APIError as e:
                if e.code in (429, 503) and len(models) > 1:
                    await self.emit({"type": "warning", "code": "model_busy", "data": {"from": models[0], "to": models[1]},
                                      "text": f"{models[0]} is busy, switching to {models[1]}"})
                    models.pop(0)
                    continue
                raise
        raise RuntimeError("no model available")

    async def _run_llm(self, s: Session, favourites_text: str) -> None:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        tools = [types.Tool(function_declarations=[types.FunctionDeclaration(**t) for t in TOOLS])]
        known = "; ".join(f"{name} (id {i})" for i, name in s.favourites.items()) or "none"
        prompt = (f"Learner's favourites (free text): {favourites_text or '(none)'}\n"
                  f"Already resolved favourites: {known}\n"
                  f"Estimated Spanish vocabulary: {s.vocab_size} lemmas.")
        contents: list = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM, tools=tools, temperature=0.2,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        models = list(config.GEMINI_MODELS)
        self.deadline = time.monotonic() + MODEL_BUDGET_S
        for _ in range(MAX_TURNS):
            resp = await self._generate(client, models, contents, cfg)
            calls = resp.function_calls or []
            if not calls:
                if resp.text:
                    await self.emit({"type": "message", "text": resp.text.strip()})
                break
            contents.append(resp.candidates[0].content)
            parts = []
            for call in calls:
                result = await self._call(s, call.name, dict(call.args or {}))
                parts.append(types.Part.from_function_response(name=call.name, response={"result": json.loads(
                    json.dumps(result, default=str))}))
            contents.append(types.Content(role="user", parts=parts))  # the API rejects role "tool"
            if s.result is not None:
                break  # ranked: the learner sees the result now; no closing message is needed
