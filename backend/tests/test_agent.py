import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import agent as agent_mod  # noqa: E402
from app.catalog import Catalog, Measured  # noqa: E402
from app.qloo import QlooClient  # noqa: E402

GRID_LEN = 32


def m(imdb, qid, cov, need):
    return Measured(imdb=imdb, wikidata="Q", kind="film", title_es=f"Peli {imdb}", title_en=None, year=2010,
                    countries=["ESP"], coverage=[cov] * GRID_LEN, vocab_for_95=need, vocab_for_98=None, qloo_id=qid)


def ent(eid, name, aff, expl=None):
    return {"entity_id": eid, "name": name, "subtype": "urn:entity:movie", "popularity": 0.5,
            "query": {"affinity": aff, "explainability": {"signal.interests.entities": expl or []}}}


AUDIO_TAGS = {"latin": [{"id": "urn:tag:genre:music:latin", "name": "Latin"}],
              "reggaeton": [{"id": "urn:tag:genre:music:reggaeton", "name": "Reggaeton"}],
              "spanish": [{"id": "urn:tag:genre:music:spanish_rock", "name": "Spanish Rock"},
                          {"id": "urn:tag:genre:music:spanish_harlem", "name": "Harlem Spanish-ish"}]}


def handler(request: httpx.Request):
    p = dict(request.url.params)
    if request.url.path == "/v2/tags":
        if p.get("filter.tag.types") != "urn:tag:genre:music":
            return httpx.Response(200, json={"results": {"tags": []}})  # no podcast language tags
        return httpx.Response(200, json={"results": {"tags": AUDIO_TAGS.get(p["filter.query"], [])}})
    if p.get("filter.type") == "urn:entity:artist":
        assert set(p["filter.tags"].split(",")) >= {"urn:tag:genre:music:latin", "urn:tag:genre:music:reggaeton"}
        return httpx.Response(200, json={"results": {"entities": [
            {"entity_id": "A-ROSALIA", "name": "Rosalía", "subtype": "urn:entity:artist", "popularity": 0.9,
             "tags": [{"id": "urn:tag:genre:music:latin", "name": "Latin"},
                      {"id": "urn:tag:genre:music:flamenco_pop", "name": "Flamenco Pop"}],
             "query": {"affinity": 0.8, "explainability": {"signal.interests.entities": [
                 {"entity_id": "FAV-Bad Bunny", "score": 0.9}]}}},
            # Tagged "Latin" by Qloo but sings in French: must not reach the Spanish music lane.
            {"entity_id": "A-KENDJI", "name": "Kendji Girac", "subtype": "urn:entity:artist", "popularity": 0.7,
             "tags": [{"id": "urn:tag:genre:music:latin", "name": "Latin"},
                      {"id": "urn:tag:genre:music:latin_pop", "name": "Latin Pop"},
                      {"id": "urn:tag:genre:music:french_pop", "name": "French Pop"}],
             "query": {"affinity": 0.79}}]}})
    if request.url.path == "/search":
        q = p["query"]
        return httpx.Response(200, json={"results": [{"entity_id": f"FAV-{q}", "name": q, "subtype": "urn:entity:tv_show"}]})
    if p.get("filter.results.entities"):
        ids = p["filter.results.entities"].split(",")
        return httpx.Response(200, json={"results": {"entities": [ent(i, f"scored {i}", 0.6) for i in ids]}})
    assert p["filter.release_country"].startswith("Spain,Mexico")
    if p["filter.type"] == "urn:entity:movie":
        return httpx.Response(200, json={"results": {"entities": [
            ent("Q-EASY", "Easy", 0.7, [{"entity_id": "FAV-Breaking Bad", "score": 0.8}]),
            ent("Q-HARD", "Hard", 0.95, [{"entity_id": "FAV-Radiohead", "score": 0.6}]),
            {**ent("Q-NEW", "Not measured", 0.9), "properties": {"country_of_origin": ["Mexico"]}},
            ent("Q-UNKNOWN", "No language evidence", 0.99),  # unverifiable: dropped
        ]}})
    return httpx.Response(200, json={"results": {"entities": []}})


def test_fixed_plan_end_to_end(monkeypatch):
    monkeypatch.setattr(agent_mod.config, "GEMINI_API_KEY", "")
    agent_mod._AUDIO_TAG_CACHE.clear()
    catalog = Catalog([m("tt1", "Q-EASY", 0.97, 2000), m("tt2", "Q-HARD", 0.86, 9000), m("tt3", "Q-MID", 0.93, 5000)])
    events = []

    async def emit(e):
        events.append(e)

    async def go():
        q = QlooClient(api_key="k", cache_dir=None, transport=httpx.MockTransport(handler))
        return await agent_mod.ComprendeAgent(q, catalog, emit).run("Breaking Bad, Radiohead", {}, vocab_size=3000)

    out = asyncio.run(go())
    assert out["mode"] == "fallback"
    assert [p["imdb"] for p in out["buckets"]["watch_now"]] == ["tt1"]
    assert out["buckets"]["watch_now"][0]["because"] == ["Breaking Bad"]
    assert [p["imdb"] for p in out["buckets"]["stretch"]] == ["tt3"]
    assert out["held_back"]["imdb"] == "tt2" and out["held_back"]["because"] == ["Radiohead"]
    assert [p["name"] for p in out["buckets"]["unmeasured"]] == ["Not measured"]
    assert any("Breaking Bad" in e["text"] for e in events if e["type"] == "step")
    # 2 searches + films (recommend, score) + series (recommend); no measured series, so no series scoring call;
    # audio: tag lookups for artists (10 queries) + 1 artist recommendation; podcasts are off (no queries)
    assert out["qloo_calls"] == 5 + 10 + 1


def test_audio_lane_uses_only_tags_that_match_and_stays_empty_without_them(monkeypatch):
    monkeypatch.setattr(agent_mod.config, "GEMINI_API_KEY", "")
    agent_mod._AUDIO_TAG_CACHE.clear()

    async def emit(e):
        return None

    async def go():
        q = QlooClient(api_key="k", cache_dir=None, transport=httpx.MockTransport(handler))
        return await agent_mod.ComprendeAgent(q, Catalog([]), emit).run("Bad Bunny", {}, 3000)

    out = asyncio.run(go())
    artists = out["listen"]["artists"]
    assert [a["name"] for a in artists] == ["Rosalía"]
    assert artists[0]["because"] == ["Bad Bunny"] and artists[0]["spanish_tags"] == ["Latin"]
    assert out["listen"]["podcasts"] == []  # no Spanish podcast tags found: nothing guessed
    tags = {t["name"] for t in agent_mod._AUDIO_TAG_CACHE["artist"]}
    assert "Harlem Spanish-ish" in tags or "Spanish Rock" in tags  # name-contains match is deliberate


def test_excluded_titles_never_come_back(monkeypatch):
    monkeypatch.setattr(agent_mod.config, "GEMINI_API_KEY", "")
    catalog = Catalog([m("tt1", "Q-EASY", 0.97, 2000), m("tt2", "Q-HARD", 0.86, 9000), m("tt3", "Q-MID", 0.93, 5000)])

    async def emit(e):
        return None

    async def go():
        q = QlooClient(api_key="k", cache_dir=None, transport=httpx.MockTransport(handler))
        return await agent_mod.ComprendeAgent(q, catalog, emit).run("Breaking Bad", {}, 3000, exclude_ids=["Q-EASY"])

    out = asyncio.run(go())
    shown = [p["qloo_id"] for b in out["buckets"].values() for p in b]
    assert "Q-EASY" not in shown and out["buckets"]["watch_now"] == []


def test_slow_model_switches_then_gives_up_within_budget(monkeypatch):
    import time

    import google.genai.errors  # noqa: F401  (warm the import so it is not timed)

    monkeypatch.setattr(agent_mod, "MODEL_CALL_TIMEOUT_S", 0.05)
    calls = []

    class SlowModels:
        async def generate_content(self, model, contents, config):
            calls.append(model)
            await asyncio.sleep(1)

    class FakeClient:
        class aio:
            models = SlowModels()

    events = []

    async def emit(e):
        events.append(e)

    async def go():
        ag = agent_mod.ComprendeAgent(None, Catalog([]), emit)
        ag.deadline = time.monotonic() + 5
        await ag._generate(FakeClient(), ["fast-model", "backup-model"], [], None)

    import pytest
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        asyncio.run(go())
    assert calls == ["fast-model", "backup-model"]          # switched once, then stopped
    assert time.monotonic() - started < 0.5                  # bounded by the per-call timeout
    assert any("slow" in e["text"] for e in events)


def test_qloo_outage_is_reported_not_disguised_as_no_match(monkeypatch):
    monkeypatch.setattr(agent_mod.config, "GEMINI_API_KEY", "")
    agent_mod._AUDIO_TAG_CACHE.clear()

    async def emit(e):
        return None

    async def go():
        q = QlooClient(api_key="", cache_dir=None, transport=httpx.MockTransport(handler))
        return await agent_mod.ComprendeAgent(q, Catalog([]), emit).run("Breaking Bad", {}, 3000)

    out = asyncio.run(go())
    assert out["qloo_unavailable"] is True and out["qloo_errors"] == ["QLOO_NO_KEY"]


def test_english_coproductions_are_dropped_but_spanish_ones_kept(monkeypatch):
    monkeypatch.setattr(agent_mod.config, "GEMINI_API_KEY", "")
    agent_mod._AUDIO_TAG_CACHE.clear()

    def h(request: httpx.Request):
        p = dict(request.url.params)
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [{"entity_id": "FAV", "name": "Radiohead", "subtype": "urn:entity:artist"}]})
        if request.url.path == "/v2/tags":
            return httpx.Response(200, json={"results": {"tags": []}})
        if p.get("filter.type") != "urn:entity:movie":
            return httpx.Response(200, json={"results": {"entities": []}})
        return httpx.Response(200, json={"results": {"entities": [
            # English-language co-production with Spain: must be dropped
            {"entity_id": "ENEMY", "name": "Enemy", "subtype": "urn:entity:movie", "query": {"affinity": 0.92},
             "properties": {"country_of_origin": ["Canada", "Spain", "France"]}, "external": {"imdb": [{"id": "tt2316411"}]}},
            # Spanish-original per Wikidata list, multinational: kept
            {"entity_id": "MONOS", "name": "Monos", "subtype": "urn:entity:movie", "query": {"affinity": 0.86},
             "properties": {"country_of_origin": ["Colombia", "Netherlands"]}, "external": {"imdb": [{"id": "tt6062774"}]}},
            # Not in the list but every country is Spanish-speaking: kept
            {"entity_id": "TOPO", "name": "El Topo", "subtype": "urn:entity:movie", "query": {"affinity": 0.86},
             "properties": {"country_of_origin": ["Mexico"]}, "external": {"imdb": [{"id": "tt0067866"}]}},
        ]}})

    async def emit(e):
        return None

    async def go():
        q = QlooClient(api_key="k", cache_dir=None, transport=httpx.MockTransport(h))
        cat = Catalog([], spanish_ids={"tt6062774"})
        return await agent_mod.ComprendeAgent(q, cat, emit).run("Radiohead", {}, 3000)

    out = asyncio.run(go())
    shown = {p["name"] for b in out["buckets"].values() for p in b}
    assert shown == {"Monos", "El Topo"}


def test_because_names_a_favourite_only_when_it_stands_out():
    from app.qloo import Entity
    favs = {"a": "Breaking Bad", "b": "Bad Bunny", "c": "Zelda"}

    def e(scores):
        return Entity.from_api(ent("x", "X", 0.8, [{"entity_id": k, "score": v} for k, v in scores.items()]))

    # An even split across three favourites is not a reason to name any one of them.
    assert agent_mod._because(e({"a": 0.35, "b": 0.34, "c": 0.31}), favs) == []
    # A clearly dominant favourite is named.
    assert agent_mod._because(e({"b": 0.52, "a": 0.24, "c": 0.24}), favs) == ["Bad Bunny"]
    # With a single favourite it is always the reason.
    assert agent_mod._because(e({"c": 1.0}), favs) == ["Zelda"]


def test_spanish_name_replaces_qloo_english_title():
    cat = Catalog([], spanish_names={"tt5674718": "Las chicas del cable"})
    assert cat.spanish_name(["tt0000001", "tt5674718"]) == "Las chicas del cable"
    assert cat.spanish_name(["tt0000001"]) is None


def test_fallback_keeps_finished_model_work():
    calls = []

    def h(req):
        calls.append(req.url.path)
        return httpx.Response(200, json={"results": {"entities": []}})

    async def emit(e):
        return None

    async def go():
        q = QlooClient(api_key="k", cache_dir=None, transport=httpx.MockTransport(h))
        a = agent_mod.ComprendeAgent(q, Catalog([]), emit)
        s = agent_mod.Session(vocab_size=3000, favourites={"x": "Breaking Bad"})
        s.done = {("recommend_spanish_titles", "movie"), ("score_measured_titles", "movie"),
                  ("recommend_spanish_titles", "tv_show"), ("score_measured_titles", "tv_show"),
                  ("recommend_spanish_audio", "artist")}
        await a._run_fixed(s, "Breaking Bad")
        return s

    s = asyncio.run(go())
    assert calls == []  # nothing fetched twice
    assert s.result is not None


def test_wikipedia_language_overrides_spanish_countries():
    # White Lines: produced in Spain, but mainly in English.
    cat = Catalog([], not_spanish={"tt9073958"})
    assert not cat.is_spanish_original(["tt9073958"], ["Spain"])
    assert cat.is_spanish_original(["tt0000001"], ["Spain"])


def test_sings_spanish_needs_a_spanish_genre_and_no_other_language_genre():
    assert agent_mod.sings_spanish(["Latin", "Reggaeton"])
    assert agent_mod.sings_spanish(["Spanish", "Spanish Pop Ballad", "French"])  # Raphael: plain "French" is noise
    assert not agent_mod.sings_spanish(["Latin"])  # Kouz-1, Dry: the broad tag alone proves nothing
    assert not agent_mod.sings_spanish(["Latin Pop", "French Pop"])  # Kendji Girac
    assert not agent_mod.sings_spanish(["Latin", "French Chanson", "Gypsy Jazz"])  # Zoufris Maracas
    assert not agent_mod.sings_spanish(["Latin Pop", "MPB"])  # Brazilian, sung in Portuguese
    assert not agent_mod.sings_spanish(["French", "Salsa", "French Caribbean Zouk"])  # Zouk Machine
    assert not agent_mod.sings_spanish(["Reggaeton", "Dub", "Downtempo", "Trip Hop"])  # Flox: mostly instrumental
