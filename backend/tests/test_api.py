import json
import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import agent as agent_mod  # noqa: E402
from app import main  # noqa: E402
from app.catalog import Catalog  # noqa: E402
from app.qloo import QlooClient  # noqa: E402
from tests.test_agent import handler, m  # noqa: E402


def setup(monkeypatch):
    monkeypatch.setattr(agent_mod.config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(main, "qloo", QlooClient(api_key="k", cache_dir=None, transport=httpx.MockTransport(handler)))
    cat = Catalog([m("tt1", "Q-EASY", 0.97, 2000), m("tt2", "Q-HARD", 0.86, 9000)])
    monkeypatch.setattr(main, "load_catalog", lambda: cat)
    main._runs.clear()
    return TestClient(main.app)


def events(resp):
    return [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]


def test_health(monkeypatch):
    c = setup(monkeypatch)
    h = c.get("/api/health").json()
    assert h["measured_titles"] == 2 and h["measured_titles_mapped_to_qloo"] == 2


def test_fake_qloo_off_unless_explicitly_enabled(monkeypatch):
    c = setup(monkeypatch)
    assert c.get("/api/health").json()["fake_qloo"] is False


def test_search_proxies_qloo(monkeypatch):
    c = setup(monkeypatch)
    r = c.get("/api/search", params={"q": "Volver"}).json()
    assert r["results"][0]["name"] == "Volver"
    assert c.get("/api/search", params={"q": "V"}).json() == {"results": []}


def test_recommend_streams_steps_then_result(monkeypatch):
    c = setup(monkeypatch)
    r = c.post("/api/recommend", json={"favourites_text": "Breaking Bad", "vocab_size": 3000})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    ev = events(r)
    assert ev[0]["type"] == "step"
    kinds = [e["type"] for e in ev]
    assert "result" in kinds and set(kinds[:kinds.index("result")]) <= {"step", "warning"}
    res = ev[kinds.index("result")]["result"]
    assert res["buckets"]["watch_now"][0]["imdb"] == "tt1"
    assert res["held_back"]["imdb"] == "tt2"


def test_recommend_validates_input(monkeypatch):
    c = setup(monkeypatch)
    assert c.post("/api/recommend", json={"favourites_text": " ", "vocab_size": 3000}).status_code == 400
    assert c.post("/api/recommend", json={"favourites_text": "x", "vocab_size": 999999}).status_code == 422


def test_rate_limit(monkeypatch):
    c = setup(monkeypatch)
    monkeypatch.setattr(main, "RUNS_PER_10_MIN", 2)
    body = {"favourites_text": "Breaking Bad", "vocab_size": 3000}
    assert c.post("/api/recommend", json=body).status_code == 200
    assert c.post("/api/recommend", json=body).status_code == 200
    assert c.post("/api/recommend", json=body).status_code == 429


def test_rate_limit_counts_forwarded_client_only_from_trusted_proxy(monkeypatch):
    c = setup(monkeypatch)
    monkeypatch.setattr(main, "RUNS_PER_10_MIN", 1)
    monkeypatch.setenv("PROXY_SECRET", "s3cret")
    body = {"favourites_text": "Breaking Bad", "vocab_size": 3000}
    proxy = {"X-Comprende-Proxy": "s3cret"}
    assert c.post("/api/recommend", json=body, headers={**proxy, "X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert c.post("/api/recommend", json=body, headers={**proxy, "X-Forwarded-For": "2.2.2.2"}).status_code == 200
    assert c.post("/api/recommend", json=body, headers={**proxy, "X-Forwarded-For": "1.1.1.1"}).status_code == 429
    # Without the secret a spoofed header is ignored: the direct client is limited as itself.
    main._runs.clear()
    assert c.post("/api/recommend", json=body, headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 200
    assert c.post("/api/recommend", json=body, headers={"X-Forwarded-For": "8.8.8.8"}).status_code == 429
