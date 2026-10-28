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

from . import config, openrouter, quota
from .catalog import Catalog
from .explainer import explain, tag_names
from .qloo import Entity, QlooClient, QlooError
from .ranker import Candidate, rank

SPANISH_RELEASE_COUNTRIES = ["Spain", "Mexico", "Argentina", "Colombia", "Chile", "Peru", "Uruguay",
                             "Venezuela", "Cuba", "Ecuador", "Bolivia", "Paraguay", "Guatemala",
                             "Dominican Republic", "Puerto Rico", "Costa Rica", "Panama"]
# Which Spanish the learner wants to hear. Accents and vocabulary differ between Spain and Latin America,
# so the choice narrows Qloo's release-country filter and the measured titles alike. Co-productions count
# for every country that produced them.
VARIETIES = {"any": SPANISH_RELEASE_COUNTRIES, "spain": ["Spain"],
             "latam": [c for c in SPANISH_RELEASE_COUNTRIES if c != "Spain"]}
LATAM_ISO3 = {"MEX", "ARG", "COL", "CHL", "PER", "URY", "VEN", "CUB", "ECU", "BOL", "PRY", "GTM", "HND", "SLV",
              "NIC", "CRI", "PAN", "DOM", "PRI"}


def in_variety(countries: list[str], variety: str) -> bool:
    """Production countries (ISO 3166 alpha-3, as in the catalog) match the chosen Spanish."""
    if variety == "spain":
        return "ESP" in countries
    if variety == "latam":
        return bool(LATAM_ISO3 & set(countries))
    return True


KINDS = {"movie": "urn:entity:movie", "tv_show": "urn:entity:tv_show", "artist": "urn:entity:artist",
         "book": "urn:entity:book", "videogame": "urn:entity:videogame", "podcast": "urn:entity:podcast",
         "brand": "urn:entity:brand", "person": "urn:entity:person"}
# What a learner means by "something you love": searching every Qloo type returned bars and shops first
# ("casa del papel" -> Casa del Mitreo, a place), so favourites are looked up among these unless asked otherwise.
MEDIA_TYPES = [KINDS[k] for k in ("tv_show", "movie", "artist", "videogame", "book", "podcast")]
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
MODEL_CALL_TIMEOUT_S = float(os.environ.get("MODEL_CALL_TIMEOUT_S", "8"))
MODEL_BUDGET_S = float(os.environ.get("MODEL_BUDGET_S", "25"))  # model time only; Qloo tool time is not counted

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
    """The favourites Qloo credits for this pick, strongest first.

    Qloo's explainability scores sum to about 1 across the signals. When one favourite clearly stands
    out (well above an even split) it alone is named. Otherwise every favourite that contributes a real
    share is named, so a learner who gave "La casa de papel" and "Breaking Bad" sees both counted rather
    than an arbitrary one ("because you like Zelda" on a prison drama). Empty when Qloo gave no scores."""
    scored = sorted(((x.get("score") or 0, favourites[x["entity_id"]]) for x in e.explainability
                     if x.get("entity_id") in favourites and favourites[x["entity_id"]]), reverse=True)
    if len(scored) <= 1:
        return [name for _, name in scored]
    even = 1 / len(scored)
    dominant = [name for score, name in scored if score >= max(0.42, 1.3 * even)]
    if dominant:
        return dominant[:2]
    return [name for score, name in scored if score >= 0.6 * even][:3]


def sings_spanish(tag_names: list[str]) -> bool:
    """True when an artist's Qloo genres say Spanish-language music (see SPANISH_GENRES)."""
    return (any(SPANISH_GENRES.search(n) for n in tag_names)
            and not any(OTHER_LANGUAGE_GENRES.search(n) for n in tag_names))


def _imdb_ids(e: Entity) -> list[str]:
    imdb = e.external.get("imdb") or []
    imdb = [imdb] if isinstance(imdb, dict) else imdb  # a list in insights rows, one object in search results
    return [x.get("id") for x in imdb if isinstance(x, dict) and x.get("id")]


@dataclass
class Session:
    vocab_size: int
    favourites: dict[str, str] = field(default_factory=dict)  # qloo id -> name
    candidates: list[Candidate] = field(default_factory=list)
    excluded: set[str] = field(default_factory=set)
    listen: list[dict] = field(default_factory=list)
    result: dict | None = None
    done: set[tuple[str, str]] = field(default_factory=set)  # (tool, kind) calls that completed
    variety: str = "any"  # any | spain | latam, see VARIETIES
    seen: dict[str, str] = field(default_factory=dict)  # every search match: qloo id -> display name


class ComprendeAgent:
    def __init__(self, qloo: QlooClient, catalog: Catalog, emit: Emit):
        self.qloo, self.catalog, self.emit = qloo, catalog, emit
        self.model_used: str | None = None
        self.model_time_left = float("inf")
        self.qloo_errors: list[str] = []

    # ---- tools ---------------------------------------------------------------

    async def find_entity(self, s: Session, query: str, kind: str | None = None) -> dict:
        await self.emit({"type": "step", "tool": "find_entity", "text": f"Looking up “{query}” in Qloo",
                         "data": {"query": query}})
        types = [KINDS[kind]] if kind in KINDS else MEDIA_TYPES
        rows = await self.qloo.search(query, types, take=5)
        if not rows and types:
            rows = await self.qloo.search(query, None, take=5)
        for r in rows:
            # A Spanish favourite is shown by its original title: "La casa de papel", not "Money Heist".
            s.seen.setdefault(r.entity_id, self.catalog.spanish_name(_imdb_ids(r), r.akas_es) or r.name)
        if rows:
            s.favourites.setdefault(rows[0].entity_id, s.seen[rows[0].entity_id])
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
            "filter.release_country": VARIETIES.get(s.variety, SPANISH_RELEASE_COUNTRIES),
            "operator.filter.release_country": "union",
            "feature.explainability": True, "take": 40,
        })
        spanish = [r for r in rows if self.catalog.match(r.entity_id, _imdb_ids(r))
                   or self.catalog.is_spanish_original(_imdb_ids(r), r.countries)]
        if s.variety != "any":
            # Qloo's filter is on release countries; the chosen Spanish is about where a title was made.
            spanish = [r for r in spanish if self._made_in_variety(r, s.variety)]
        added = self._add(s, spanish, kind)
        measured = sum(1 for c in added if c.measured)
        return {"returned": len(rows), "dropped_not_spanish_original": len(rows) - len(spanish),
                "with_measured_difficulty": measured, "top": [c.name for c in added[:8]]}

    async def score_measured_titles(self, s: Session, signal_entity_ids: list[str], kind: str) -> dict:
        label = "films" if kind == "movie" else "series"
        want = "film" if kind == "movie" else "series"
        # The best-known measured titles (catalog order), capped to keep a run within ~8 Qloo calls per type.
        ids = [t.qloo_id for t in self.catalog.titles
               if t.qloo_id and t.kind == want and in_variety(t.countries, s.variety)][:MAX_SCORED_PER_TYPE]
        if not ids:
            return {"scored": 0, "top": [], "note": f"no measured {label} are mapped to Qloo yet"}
        await self.emit({"type": "step", "tool": "score_measured_titles",
                         "text": f"Scoring {len(ids)} {label} with measured dialogue against your taste",
                         "data": {"kind": kind, "count": len(ids)}})
        self._remember(s, signal_entity_ids)
        # Batches of 50 are independent requests: send them together (8 sequential calls took 5-7 s).
        batches = await asyncio.gather(*(self.qloo.insights(**{
            "filter.type": KINDS[kind], "signal.interests.entities": signal_entity_ids,
            "filter.results.entities": ids[i:i + 50], "feature.explainability": True, "take": 50,
        }) for i in range(0, len(ids), 50)), return_exceptions=True)
        failed = [b for b in batches if isinstance(b, BaseException)]
        if len(failed) == len(batches):
            raise failed[0]
        # A batch Qloo refused leaves those titles unscored; the others still count.
        rows: list[Entity] = [r for batch in batches if not isinstance(batch, BaseException) for r in batch]
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
        # The model may signal with a lower search match than the first: name it as Qloo did. An id that
        # never came back from a search still counts as a signal but is never shown as a name.
        for i in ids:
            s.favourites.setdefault(i, s.seen.get(i, ""))

    def _made_in_variety(self, r: Entity, variety: str) -> bool:
        m = self.catalog.match(r.entity_id, _imdb_ids(r))
        if m:
            return in_variety(m.countries, variety)
        return not r.countries or any(c in VARIETIES[variety] for c in r.countries)

    def _add(self, s: Session, rows: list[Entity], kind: str) -> list[Candidate]:
        out = []
        for r in rows:
            imdb = _imdb_ids(r)
            because = _because(r, s.favourites)
            measured = self.catalog.match(r.entity_id, imdb)
            c = Candidate(qloo_id=r.entity_id, name=self.catalog.spanish_name(imdb) or r.name,
                          kind="film" if kind == "movie" else "series",
                          year=r.year, image=r.image, description=r.description, affinity=r.affinity,
                          popularity=r.popularity, because=[b for b in because if b],
                          tags=tag_names(r.tags), traits=r.traits,
                          measured=measured,
                          pace=self.catalog.pace(measured, r.duration) if measured else (None, None))
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
            if e.code not in self.qloo_errors:  # one line per kind of failure, not one per call
                await self.emit({"type": "warning", "code": "qloo", "data": {"code": e.code},
                                 "text": f"Qloo did not answer ({e.code})"})
            self.qloo_errors.append(e.code)
            return {"error": e.code, "retryable": e.retryable}

    async def explain_picks(self, result: dict) -> dict:
        """Second agent: one specific, translated reason per pick shown, from Qloo's description of it."""
        s = self.session
        shown = [p for b in ("watch_now", "stretch") for p in result["buckets"][b]]
        if result.get("held_back"):
            shown.append(result["held_back"])
        if not shown or not (config.GEMINI_API_KEY or config.OPENROUTER_API_KEY):
            return {}
        await self.emit({"type": "step", "tool": "explain_picks", "text": "Writing a reason for each pick",
                         "data": {"count": len(shown)}})
        by_id = {c.qloo_id: c for c in s.candidates if c.qloo_id}
        return await explain(shown, by_id, [n for n in s.favourites.values() if n])

    # ---- runs ----------------------------------------------------------------

    async def run(self, favourites_text: str, favourite_ids: dict[str, str], vocab_size: int,
                  exclude_ids: list[str] | None = None, variety: str = "any") -> dict:
        s = Session(vocab_size=vocab_size, favourites=dict(favourite_ids), excluded=set(exclude_ids or []),
                    variety=variety if variety in VARIETIES else "any")
        self.session = s
        # The client is shared by all runs in this process; count only this run's requests.
        requests_before = self.qloo.calls + self.qloo.cached
        planners = [p for p, key in (("gemini", config.GEMINI_API_KEY), ("openrouter", config.OPENROUTER_API_KEY))
                    if key]
        planned, last_error = False, None
        for provider in planners:
            # A backup model only starts a run from scratch; a run the first model left half done is
            # finished by the fixed plan, which resumes from the calls already made.
            if s.done and provider != planners[0]:
                break
            try:
                await (self._run_llm(s, favourites_text) if provider == "gemini"
                       else self._run_openrouter(s, favourites_text))
                planned = True
                break
            except Exception as e:  # outage, quota or too slow: try the next provider
                last_error = e
                if provider != planners[-1] and not s.done:
                    await self.emit({"type": "warning", "code": "model_busy", "data": {"from": provider, "to": "backup"},
                                     "text": f"{provider} is unavailable, switching to a backup model"})
        mode = "agent" if planned else "fallback"
        if not planned:
            if planners:  # never leave the learner with nothing
                slow = isinstance(last_error, TimeoutError)
                state = "slow right now" if slow else "unavailable"
                await self.emit({"type": "warning", "code": "fallback", "data": {"slow": slow},
                                 "text": f"The language model is {state}; finishing with the fixed plan"})
            await self._run_fixed(s, favourites_text)
        if s.result is None:
            await self.rank_for_learner(s)
        listen = sorted(s.listen, key=lambda x: -(x["affinity"] or 0))
        return {"mode": mode, "model": self.model_used, "favourites": {i: n for i, n in s.favourites.items() if n},
                "variety": s.variety,
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

        from google.genai import types

        while models and not quota.available(models[0]):
            models.pop(0)  # daily quota spent: skip it without trying
        while models:
            if self.model_time_left <= 0:
                raise TimeoutError("model budget spent")
            level = config.GEMINI_THINKING.get(models[0])
            call_cfg = cfg.model_copy(update={"thinking_config": types.ThinkingConfig(thinking_level=level)}) if level else cfg
            started = time.monotonic()
            try:
                resp = await asyncio.wait_for(
                    client.aio.models.generate_content(model=models[0], contents=contents, config=call_cfg),
                    timeout=min(MODEL_CALL_TIMEOUT_S, self.model_time_left))
                self.model_used = models[0]
                return resp
            except asyncio.TimeoutError:
                if len(models) > 1 and self.model_time_left - (time.monotonic() - started) > 3:
                    await self.emit({"type": "warning", "code": "model_slow", "data": {"from": models[0], "to": models[1]},
                                      "text": f"{models[0]} is slow, switching to {models[1]}"})
                    models.pop(0)
                    continue
                raise TimeoutError("model too slow") from None
            except errors.APIError as e:
                if e.code == 429:
                    quota.note_error(models[0], e)
                if e.code in (429, 503) and len(models) > 1:
                    await self.emit({"type": "warning", "code": "model_busy", "data": {"from": models[0], "to": models[1]},
                                      "text": f"{models[0]} is busy, switching to {models[1]}"})
                    models.pop(0)
                    continue
                raise
            finally:
                self.model_time_left -= time.monotonic() - started
        raise RuntimeError("no model available")

    def _prompt(self, s: Session, favourites_text: str) -> str:
        known = "; ".join(f"{name} (id {i})" for i, name in s.favourites.items()) or "none"
        return (f"Learner's favourites (free text): {favourites_text or '(none)'}\n"
                f"Already resolved favourites: {known}\n"
                f"Estimated Spanish vocabulary: {s.vocab_size} lemmas.")

    async def _run_tools(self, s: Session, calls: list[tuple[str, dict]]) -> list[dict]:
        """Calls asked for in one turn are independent Qloo requests: run them together. Ranking reads
        what the others found, so it always runs after them. Results come back in the order asked."""
        now = [i for i, (name, _) in enumerate(calls) if name != "rank_for_learner"]
        later = [i for i, (name, _) in enumerate(calls) if name == "rank_for_learner"]
        results = dict(zip(now, await asyncio.gather(*(self._call(s, *calls[i]) for i in now))))
        for i in later:
            results[i] = await self._call(s, *calls[i])
        return [results[i] for i in range(len(calls))]

    async def _run_openrouter(self, s: Session, favourites_text: str) -> None:
        """Same plan-and-call loop as Gemini, with an open model through OpenRouter."""
        models = [m for m in config.OPENROUTER_MODELS if quota.available(m)]
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": self._prompt(s, favourites_text)}]
        time_left = config.OPENROUTER_BUDGET_S
        for _ in range(MAX_TURNS):
            msg = None
            while msg is None:
                if not models or time_left <= 0:
                    raise TimeoutError("backup models unavailable or too slow")
                started = time.monotonic()
                try:
                    msg = await openrouter.chat(models[0], messages, tools=TOOLS, timeout=min(20.0, time_left))
                    self.model_used = f"openrouter:{models[0]}"
                except Exception as e:  # refused, rate limited or slow: next backup model
                    quota.note_error(models[0], e)
                    models.pop(0)
                finally:
                    time_left -= time.monotonic() - started
            calls = msg.get("tool_calls") or []
            if not calls:
                if msg.get("content"):
                    await self.emit({"type": "message", "text": str(msg["content"]).strip()})
                break
            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            parsed = []
            for c in calls:
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                parsed.append((c["function"]["name"], args if isinstance(args, dict) else {}))
            for c, result in zip(calls, await self._run_tools(s, parsed)):
                messages.append({"role": "tool", "tool_call_id": c.get("id", ""),
                                 "content": json.dumps(result, default=str)})
            if s.result is not None:
                break

    async def _run_llm(self, s: Session, favourites_text: str) -> None:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        tools = [types.Tool(function_declarations=[types.FunctionDeclaration(**t) for t in TOOLS])]
        prompt = self._prompt(s, favourites_text)
        contents: list = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM, tools=tools, temperature=0.2,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        models = list(config.GEMINI_MODELS)
        self.model_time_left = MODEL_BUDGET_S
        for _ in range(MAX_TURNS):
            resp = await self._generate(client, models, contents, cfg)
            calls = resp.function_calls or []
            if not calls:
                if resp.text:
                    await self.emit({"type": "message", "text": resp.text.strip()})
                break
            contents.append(resp.candidates[0].content)
            results = await self._run_tools(s, [(c.name, dict(c.args or {})) for c in calls])
            parts = [types.Part.from_function_response(name=c.name, response={"result": json.loads(
                json.dumps(r, default=str))}) for c, r in zip(calls, results)]
            contents.append(types.Content(role="user", parts=parts))  # the API rejects role "tool"
            if s.result is not None:
                break  # ranked: the learner sees the result now; no closing message is needed
