"""DEVELOPMENT ONLY: a stand-in for the Qloo API so the interface can be built before a key exists.

Enabled only when COMPRENDE_DEV_FAKE_QLOO=1. Affinities are pseudo-random and mean nothing.
/api/health reports fake_qloo=true and the web app shows a banner, so fake output can never be
mistaken for real recommendations. Never set this variable in a deployment.
"""
import hashlib
import os

import httpx

from .catalog import load_catalog

ENABLED = os.environ.get("COMPRENDE_DEV_FAKE_QLOO") == "1"


def _score(*parts: str) -> float:
    h = hashlib.sha256("|".join(parts).encode()).digest()
    return round(0.5 + h[0] / 512, 3)


def handler(request: httpx.Request) -> httpx.Response:
    p = dict(request.url.params)
    cat = load_catalog()
    if request.url.path == "/search":
        q = p.get("query", "")
        return httpx.Response(200, json={"results": [
            {"entity_id": f"FAKE-{q.lower().replace(' ', '-')}", "name": q, "subtype": "urn:entity:tv_show"}]})
    signals = p.get("signal.interests.entities", "").split(",")
    kind = "series" if p.get("filter.type", "").endswith("tv_show") else "film"
    if p.get("filter.results.entities"):
        wanted = set(p["filter.results.entities"].split(","))
        titles = [t for t in cat.titles if t.qloo_id in wanted]
    else:
        titles = [t for t in cat.titles if t.kind == kind][:40]
    rows = []
    for t in titles:
        rows.append({
            "entity_id": t.qloo_id or f"FAKE-{t.imdb}", "name": t.title_es or t.title_en, "subtype": f"urn:entity:{kind}",
            "properties": {"release_year": t.year},
            "external": {"imdb": [{"id": t.imdb}]},
            "popularity": 0.5,
            "query": {"affinity": _score(t.imdb, *signals),
                      "explainability": {"signal.interests.entities": [
                          {"entity_id": s, "score": _score(s, t.imdb)} for s in signals if s]}},
        })
    return httpx.Response(200, json={"results": {"entities": rows}})


transport = httpx.MockTransport(handler) if ENABLED else None
