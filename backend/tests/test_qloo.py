import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.qloo import Entity, QlooClient, QlooError  # noqa: E402

# Shapes taken from the Qloo docs (Schema & Taxonomy page and Insights reference).
FLAT_MOVIE = {
    "entity_id": "18B098FD-3D84-4609-BFF3-ADF9A0B00E40", "type": "urn:entity", "subtype": "urn:entity:movie",
    "name": "Inception", "release_year": 2010, "country_of_origin": ["United States", "United Kingdom"],
    "url": "https://images.qloo.com/i/x.jpg", "popularity": 0.99, "affinity": 0.90,
    "short_description": "A thief plants an idea.",
    "tags": [{"id": "urn:tag:genre:media:action", "name": "Action", "type": "urn:tag:genre:media"}],
}
NESTED_MOVIE = {
    "entity_id": "AAAA", "name": "El laberinto del fauno", "subtype": "urn:entity:movie",
    "properties": {"release_year": 2006, "country_of_origin": ["Spain", "Mexico"], "image": {"url": "https://img/x.jpg"},
                   "description": "Una niña..."},
    "popularity": 0.95,
    "query": {"affinity": 0.81, "explainability": {"signal.interests.entities": [{"entity_id": "BBBB", "score": 0.7}]}},
    "external": {"imdb": [{"id": "tt0457430"}]},
}


def run(coro):
    return asyncio.run(coro)


def client_with(handler, tmp_path=None, key="test-key"):
    return QlooClient(api_key=key, base_url="https://hackathon.api.qloo.com",
                      cache_dir=tmp_path, transport=httpx.MockTransport(handler))


def test_entity_flat_and_nested_shapes():
    a = Entity.from_api(FLAT_MOVIE)
    assert (a.name, a.year, a.affinity, a.image) == ("Inception", 2010, 0.90, "https://images.qloo.com/i/x.jpg")
    assert a.countries == ["United States", "United Kingdom"] and a.tags[0]["name"] == "Action"
    b = Entity.from_api(NESTED_MOVIE)
    assert (b.year, b.affinity, b.image) == (2006, 0.81, "https://img/x.jpg")
    assert b.countries == ["Spain", "Mexico"]
    assert b.explainability == [{"entity_id": "BBBB", "score": 0.7}]
    assert b.external["imdb"][0]["id"] == "tt0457430"


def test_insights_sends_header_and_flattens_lists():
    seen = {}

    def handler(request: httpx.Request):
        seen["key"] = request.headers.get("x-api-key")
        seen["params"] = dict(request.url.params)
        seen["path"] = request.url.path
        return httpx.Response(200, json={"success": True, "results": {"entities": [NESTED_MOVIE]}})

    c = client_with(handler)
    rows = run(c.insights(**{"filter.type": "urn:entity:movie", "filter.release_country": ["Spain", "Mexico"],
                             "signal.interests.entities": ["A", "B"], "feature.explainability": True, "take": 20}))
    assert seen["path"] == "/v2/insights" and seen["key"] == "test-key"
    assert seen["params"]["filter.release_country"] == "Spain,Mexico"
    assert seen["params"]["signal.interests.entities"] == "A,B"
    assert seen["params"]["feature.explainability"] == "true"
    assert rows[0].name == "El laberinto del fauno"


def test_auth_error_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, json={"error": {"reason": "API keys mismatch", "message": "Unauthorized", "code": 401}})

    with pytest.raises(QlooError) as e:
        run(client_with(handler).search("Volver"))
    assert e.value.code == "QLOO_AUTH" and "API keys mismatch" in e.value.message
    assert len(calls) == 1


def test_rate_limit_retried_then_succeeds(monkeypatch):
    responses = [httpx.Response(429, json={"message": "slow down"}),
                 httpx.Response(200, json={"success": True, "results": [FLAT_MOVIE]})]

    async def no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    c = client_with(lambda r: responses.pop(0))
    rows = run(c.search("Inception"))
    assert rows[0].name == "Inception" and c.calls == 2


def test_disk_cache_avoids_second_request(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"success": True, "results": [FLAT_MOVIE]})

    c = client_with(handler, tmp_path)
    run(c.search("Inception"))
    run(c.search("Inception"))
    assert len(calls) == 1
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert "test-key" not in next(tmp_path.glob("*.json")).read_text()


def test_missing_key_fails_clearly():
    with pytest.raises(QlooError) as e:
        run(client_with(lambda r: httpx.Response(200, json={}), key="").search("x"))
    assert e.value.code == "QLOO_NO_KEY"


def test_entities_by_external_ids():
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"success": True, "results": [NESTED_MOVIE]})

    rows = run(client_with(handler).entities_by_external("imdb", ["tt0457430", "tt0441909"]))
    assert seen == {"external.imdb.ids": "tt0457430,tt0441909"}
    assert rows[0].entity_id == "AAAA"
