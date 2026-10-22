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


def handler(request: httpx.Request):
    p = dict(request.url.params)
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
            ent("Q-NEW", "Not measured", 0.9),
        ]}})
    return httpx.Response(200, json={"results": {"entities": []}})


def test_fixed_plan_end_to_end(monkeypatch):
    monkeypatch.setattr(agent_mod.config, "GEMINI_API_KEY", "")
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
    assert out["buckets"]["unmeasured"][0]["name"] == "Not measured"
    assert any("Breaking Bad" in e["text"] for e in events if e["type"] == "step")
    # 2 searches + films (recommend, score) + series (recommend); no measured series, so no series scoring call
    assert out["qloo_calls"] == 5


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
