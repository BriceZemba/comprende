"""Qloo API client.

Server-side only: the key never reaches the browser. Responses are cached on disk
(keyed by path and parameters) so repeated demo runs cost no quota and stay fast.
"""
import asyncio
import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from . import config

CACHE_TTL_S = 7 * 24 * 3600
# Qloo answers in 1-3 s. When it cannot be reached or hangs, later calls fail at once for a short while instead
# of each waiting out its own timeout, so a run ends in seconds with a clear message rather than in minutes.
TIMEOUT = httpx.Timeout(12.0, connect=6.0)
UNREACHABLE_PAUSE_S = 30.0
# Qloo refuses bursts (429): three simultaneous runs, ~30 parallel calls each, were refused in production.
# One process keeps at most this many requests in flight, and a refused call waits longer each time.
MAX_IN_FLIGHT = int(os.environ.get("QLOO_MAX_IN_FLIGHT", "6"))
ATTEMPTS = 4


class QlooError(Exception):
    def __init__(self, code: str, status: int, message: str, retryable: bool = False):
        super().__init__(f"{code} ({status}): {message}")
        self.code, self.status, self.message, self.retryable = code, status, message, retryable


@dataclass
class Entity:
    """The fields Comprende uses, read from either the flat or the `properties`-nested shape."""
    entity_id: str
    name: str
    subtype: str
    year: int | None = None
    countries: list[str] = field(default_factory=list)
    image: str | None = None
    description: str | None = None
    popularity: float | None = None
    affinity: float | None = None
    tags: list[dict] = field(default_factory=list)
    traits: dict = field(default_factory=dict)  # Qloo's own genre / themes / tone descriptions
    akas_es: list[str] = field(default_factory=list)  # titles Qloo lists for Spanish
    duration: float | None = None  # running time in minutes, for films
    explainability: list[dict] = field(default_factory=list)
    external: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, raw: dict) -> "Entity":
        props = raw.get("properties") or {}

        def get(key, default=None):
            return raw.get(key, props.get(key, default))

        image = get("image")
        if isinstance(image, dict):
            image = image.get("url")
        image = image or get("url")
        query = raw.get("query") or {}
        expl = query.get("explainability") or {}
        if isinstance(expl, dict):
            expl = expl.get("signal.interests.entities") or expl.get("entities") or []
        year = get("release_year") or get("publication_year")
        countries = get("country_of_origin") or get("release_country") or []
        if isinstance(countries, str):
            countries = [countries]
        return cls(
            entity_id=raw.get("entity_id") or raw.get("id"),
            name=raw.get("name") or get("title") or "",
            # /search lists the entity type under "types"; insights rows use "subtype" or "type".
            subtype=raw.get("subtype") or raw.get("type") or next(iter(raw.get("types") or []), ""),
            year=int(year) if year else None,
            countries=list(countries),
            image=image,
            description=get("short_description") or get("description"),
            popularity=raw.get("popularity"),
            affinity=query.get("affinity", raw.get("affinity")),
            tags=[{"id": t.get("id") or t.get("tag_id"), "name": t.get("name")} for t in (raw.get("tags") or [])],
            explainability=expl if isinstance(expl, list) else [],
            traits={k: get(f"{k}_description") for k in ("genre", "plot_themes", "emotional_tone")
                    if get(f"{k}_description")},
            duration=get("duration") if isinstance(get("duration"), (int, float)) else None,
            akas_es=[str(a.get("value", "")).strip('"') for a in (get("akas") or [])
                     if isinstance(a, dict) and "es" in (a.get("languages") or [a.get("language")])],
            external=get("external") or {},  # top level in insights rows, under properties in search
        )

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class QlooClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 cache_dir: Path | None = config.CACHE_DIR, transport: httpx.AsyncBaseTransport | None = None):
        """cache_dir=None disables the disk cache."""
        self.api_key = api_key if api_key is not None else config.QLOO_API_KEY
        self.base_url = (base_url or config.QLOO_BASE_URL).rstrip("/")
        self.cache_dir = cache_dir
        self.calls = 0  # live requests made, for the agent trace and quota tracking
        self.cached = 0  # requests answered from the disk cache (same Qloo data, no quota used)
        self._down_until = 0.0  # monotonic time until which calls fail fast (see UNREACHABLE_PAUSE_S)
        self._slots = asyncio.Semaphore(MAX_IN_FLIGHT)
        self._http = httpx.AsyncClient(
            base_url=self.base_url, timeout=TIMEOUT, transport=transport,
            headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
        )

    async def aclose(self):
        await self._http.aclose()

    # ---- low level -------------------------------------------------------

    def _cache_file(self, path: str, params: list[tuple[str, str]]) -> Path | None:
        if not self.cache_dir:
            return None
        key = hashlib.sha256(json.dumps([path, sorted(params)]).encode()).hexdigest()[:32]
        return self.cache_dir / f"{key}.json"

    async def get(self, path: str, params: dict[str, Any]) -> dict:
        flat = _flatten(params)
        cache = self._cache_file(path, flat)
        if cache and cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_S:
            self.cached += 1
            return json.loads(cache.read_text(encoding="utf-8"))
        if not self.api_key:
            raise QlooError("QLOO_NO_KEY", 0, "QLOO_API_KEY is not set")
        if time.monotonic() < self._down_until:
            raise QlooError("QLOO_UNREACHABLE", 0, "Qloo did not answer a moment ago", True)
        for attempt in range(ATTEMPTS):
            self.calls += 1
            try:
                async with self._slots:
                    resp = await self._http.get(path, params=flat)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                if attempt == 0 and not isinstance(e, httpx.TimeoutException):  # a hang is not retried
                    await asyncio.sleep(1.0)
                    continue
                self._down_until = time.monotonic() + UNREACHABLE_PAUSE_S
                raise QlooError("QLOO_UNREACHABLE", 0, type(e).__name__, True) from e
            if resp.status_code == 200:
                data = resp.json()
                if cache:
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    cache.write_text(json.dumps(data), encoding="utf-8")
                return data
            err = _error_from(resp)
            if err.retryable and attempt < ATTEMPTS - 1:
                await asyncio.sleep(_backoff(resp, attempt))
                continue
            raise err
        raise QlooError("QLOO_UNREACHABLE", 0, "retries exhausted", True)

    # ---- endpoints ---------------------------------------------------------

    async def search(self, query: str, types: list[str] | None = None, take: int = 8) -> list[Entity]:
        params: dict[str, Any] = {"query": query, "take": take}
        if types:
            params["types"] = ",".join(types)
        data = await self.get("/search", params)
        return [Entity.from_api(r) for r in data.get("results", [])]

    async def entities_by_external(self, source: str, ids: list[str]) -> list[Entity]:
        """Look up Qloo entities from external ids, e.g. source='imdb' or 'wikidata'."""
        data = await self.get("/entities", {f"external.{source}.ids": ",".join(ids)})
        return [Entity.from_api(r) for r in data.get("results", [])]

    async def tags(self, query: str, tag_types: list[str] | None = None, take: int = 20) -> list[dict]:
        """GET /v2/tags: tag ids and names whose name matches the query."""
        params: dict[str, Any] = {"filter.query": query, "take": take}
        if tag_types:
            params["filter.tag.types"] = ",".join(tag_types)
        data = await self.get("/v2/tags", params)
        results = data.get("results") or {}
        rows = results.get("tags", []) if isinstance(results, dict) else results
        return [{"id": r.get("id") or r.get("tag_id"), "name": r.get("name", ""), "type": r.get("type") or r.get("subtype")}
                for r in rows if r.get("id") or r.get("tag_id")]

    async def insights(self, **params: Any) -> list[Entity]:
        """GET /v2/insights. Pass Qloo parameter names with dots replaced by double underscores,
        or a dict via insights(**{"filter.type": ...})."""
        clean = {k.replace("__", "."): v for k, v in params.items() if v not in (None, "", [])}
        data = await self.get("/v2/insights", clean)
        results = data.get("results") or {}
        rows = results.get("entities", []) if isinstance(results, dict) else results
        return [Entity.from_api(r) for r in rows]


def _flatten(params: dict[str, Any]) -> list[tuple[str, str]]:
    out = []
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            v = ",".join(str(x) for x in v)
        elif isinstance(v, bool):
            v = "true" if v else "false"
        out.append((k, str(v)))
    return out


def _backoff(resp: httpx.Response, attempt: int) -> float:
    """Seconds before retrying a refused or failed call: Qloo's Retry-After when given (capped), else 1, 2, 4 s,
    with jitter so simultaneous runs do not retry in step."""
    try:
        after = float(resp.headers.get("retry-after", ""))
    except ValueError:
        after = 2.0 ** attempt
    return min(after, 6.0) + random.uniform(0, 0.5)


def _error_from(resp: httpx.Response) -> QlooError:
    try:
        body = resp.json()
        err = body.get("error", body)
        message = err.get("message") or err.get("reason") or resp.text[:200]
        reason = err.get("reason", "")
    except ValueError:
        message, reason = resp.text[:200], ""
    s = resp.status_code
    if s in (401, 403):
        code = "QLOO_AUTH" if s == 401 else "QLOO_FORBIDDEN"
        return QlooError(code, s, f"{reason} {message}".strip())
    if s == 429:
        return QlooError("QLOO_RATE_LIMIT", s, message, retryable=True)
    if s >= 500:
        return QlooError("QLOO_SERVER", s, message, retryable=True)
    return QlooError("QLOO_BAD_REQUEST", s, message)
