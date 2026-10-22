"""The Comprende agent.

Gemini plans and calls tools; Qloo supplies taste, the subtitle pipeline supplies
comprehension, and the deterministic ranker decides the order. The model writes the
words a learner reads (why each pick fits), never the numbers.

If Gemini is unavailable the same tools run in a fixed order, so the app keeps working.
"""
import asyncio
import json
import os
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
    "podcast": ["spanish", "español", "latino"],
}
AUDIO_TAG_TYPES = {"artist": ["urn:tag:genre:music"], "podcast": ["urn:tag:genre:media"]}
MAX_TURNS = 10
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
4. Call recommend_spanish_audio for artists and for podcasts (listening practice).
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
        "description": "Qloo recommendations of Spanish-language or Latin music artists, or podcasts, that fit the "
                       "learner's favourites. For listening practice; difficulty is not measured for these.",
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "signal_entity_ids": {"type": "array", "items": {"type": "string"}},
                "kind": {"type": "string", "enum": ["artist", "podcast"]},
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


@dataclass
class Session:
    vocab_size: int
    favourites: dict[str, str] = field(default_factory=dict)  # qloo id -> name
    candidates: list[Candidate] = field(default_factory=list)
    excluded: set[str] = field(default_factory=set)
    listen: list[dict] = field(default_factory=list)
    result: dict | None = None


class ComprendeAgent:
    def __init__(self, qloo: QlooClient, catalog: Catalog, emit: Emit):
        self.qloo, self.catalog, self.emit = qloo, catalog, emit
        self.model_used: str | None = None
        self.deadline = float("inf")

    # ---- tools ---------------------------------------------------------------

    async def find_entity(self, s: Session, query: str, kind: str | None = None) -> dict:
        await self.emit({"type": "step", "tool": "find_entity", "text": f"Looking up “{query}” in Qloo"})
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
                         "text": f"Asking Qloo for Spanish-language {label} that match your taste"})
        self._remember(s, signal_entity_ids)
        rows = await self.qloo.insights(**{
            "filter.type": KINDS[kind], "signal.interests.entities": signal_entity_ids,
            "filter.release_country": SPANISH_RELEASE_COUNTRIES, "operator.filter.release_country": "union",
            "feature.explainability": True, "take": 40,
        })
        added = self._add(s, rows, kind)
        measured = sum(1 for c in added if c.measured)
        return {"returned": len(rows), "with_measured_difficulty": measured,
                "top": [c.name for c in added[:8]]}

    async def score_measured_titles(self, s: Session, signal_entity_ids: list[str], kind: str) -> dict:
        label = "films" if kind == "movie" else "series"
        want = "film" if kind == "movie" else "series"
        ids = [t.qloo_id for t in self.catalog.titles if t.qloo_id and t.kind == want]
        if not ids:
            return {"scored": 0, "top": [], "note": f"no measured {label} are mapped to Qloo yet"}
        await self.emit({"type": "step", "tool": "score_measured_titles",
                         "text": f"Scoring {len(ids)} {label} with measured dialogue against your taste"})
        self._remember(s, signal_entity_ids)
        rows: list[Entity] = []
        for i in range(0, min(len(ids), 400), 50):
            rows += await self.qloo.insights(**{
                "filter.type": KINDS[kind], "signal.interests.entities": signal_entity_ids,
                "filter.results.entities": ids[i:i + 50], "feature.explainability": True, "take": 50,
            })
        added = self._add(s, rows, kind)
        return {"scored": len(rows), "top": [c.name for c in sorted(added, key=lambda c: -(c.affinity or 0))[:8]]}

    async def recommend_spanish_audio(self, s: Session, signal_entity_ids: list[str], kind: str) -> dict:
        label = "music" if kind == "artist" else "podcasts"
        await self.emit({"type": "step", "tool": "recommend_spanish_audio",
                         "text": f"Asking Qloo for Spanish-language {label} that match your taste"})
        self._remember(s, signal_entity_ids)
        tags = await self._audio_tags(kind)
        if not tags:
            return {"returned": 0, "note": f"no Spanish or Latin tags found for {label}"}
        rows = await self.qloo.insights(**{
            "filter.type": f"urn:entity:{kind}", "signal.interests.entities": signal_entity_ids,
            "filter.tags": [t["id"] for t in tags], "operator.filter.tags": "union",
            "feature.explainability": True, "take": 12,
        })
        tag_names = {t["id"]: t["name"] for t in tags}
        seen = {x["qloo_id"] for x in s.listen}
        for r in rows:
            if r.entity_id in seen or r.entity_id in s.excluded or r.entity_id in s.favourites                     or r.name.lower() in {n.lower() for n in s.favourites.values()}:
                continue  # never hand a favourite back as a recommendation
            because = [s.favourites.get(e.get("entity_id"), "") for e in r.explainability
                       if (e.get("score") or 0) >= 0.1 and e.get("entity_id") in s.favourites]
            s.listen.append({"qloo_id": r.entity_id, "name": r.name, "kind": kind, "image": r.image,
                             "description": r.description, "affinity": r.affinity, "because": [b for b in because if b],
                             "spanish_tags": [tag_names[t["id"]] for t in r.tags if t.get("id") in tag_names]})
        return {"returned": len(rows), "top": [r.name for r in rows[:6]]}

    async def _audio_tags(self, kind: str) -> list[dict]:
        if kind in _AUDIO_TAG_CACHE:
            return _AUDIO_TAG_CACHE[kind]
        found: dict[str, dict] = {}
        for q in AUDIO_TAG_QUERIES[kind]:
            for t in await self.qloo.tags(q, AUDIO_TAG_TYPES[kind], take=10):
                words = q.replace("ñ", "n").split()
                name = t["name"].lower().replace("ñ", "n")
                if all(w.replace("ñ", "n") in name for w in words):
                    found[t["id"]] = t
        _AUDIO_TAG_CACHE[kind] = list(found.values())
        return _AUDIO_TAG_CACHE[kind]

    async def rank_for_learner(self, s: Session) -> dict:
        await self.emit({"type": "step", "tool": "rank_for_learner",
                         "text": f"Checking each title's dialogue against your ~{s.vocab_size:,} words"})
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
            imdb = [x.get("id") for x in (r.external.get("imdb") or []) if isinstance(x, dict)]
            because = [s.favourites.get(e.get("entity_id"), "") for e in r.explainability
                       if (e.get("score") or 0) >= 0.1 and e.get("entity_id") in s.favourites]
            c = Candidate(qloo_id=r.entity_id, name=r.name, kind="film" if kind == "movie" else "series",
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
            return await fn(s, **args)
        except QlooError as e:
            await self.emit({"type": "warning", "text": f"Qloo returned {e.code}"})
            return {"error": e.code, "retryable": e.retryable}

    # ---- runs ----------------------------------------------------------------

    async def run(self, favourites_text: str, favourite_ids: dict[str, str], vocab_size: int,
                  exclude_ids: list[str] | None = None) -> dict:
        s = Session(vocab_size=vocab_size, favourites=dict(favourite_ids), excluded=set(exclude_ids or []))
        mode = "agent"
        if config.GEMINI_API_KEY:
            try:
                await self._run_llm(s, favourites_text)
            except Exception as e:  # outage, quota or too slow: fall back, never leave the learner with nothing
                why = ("is slow right now" if isinstance(e, TimeoutError)
                       else f"is unavailable ({type(e).__name__})")
                await self.emit({"type": "warning", "text": f"The language model {why}; finishing with the fixed plan"})
                mode = "fallback"
                await self._run_fixed(s, favourites_text)
        else:
            mode = "fallback"
            await self._run_fixed(s, favourites_text)
        if s.result is None:
            await self.rank_for_learner(s)
        listen = sorted(s.listen, key=lambda x: -(x["affinity"] or 0))
        return {"mode": mode, "model": self.model_used, "favourites": s.favourites, "qloo_calls": self.qloo.calls,
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
        s.candidates.clear()
        ids = list(s.favourites)[:10]
        for kind in ("movie", "tv_show"):
            await self._call(s, "recommend_spanish_titles", {"signal_entity_ids": ids, "kind": kind})
            await self._call(s, "score_measured_titles", {"signal_entity_ids": ids, "kind": kind})
        for kind in ("artist", "podcast"):
            await self._call(s, "recommend_spanish_audio", {"signal_entity_ids": ids, "kind": kind})
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
                    await self.emit({"type": "warning", "text": f"{models[0]} is slow, switching to {models[1]}"})
                    models.pop(0)
                    continue
                raise TimeoutError("model too slow") from None
            except errors.APIError as e:
                if e.code in (429, 503) and len(models) > 1:
                    await self.emit({"type": "warning", "text": f"{models[0]} is busy, switching to {models[1]}"})
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
