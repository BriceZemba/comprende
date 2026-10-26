"""Where a title can be watched, by country, from TMDB's watch-provider data (sourced from JustWatch).

Without TMDB_API_KEY the app links to a JustWatch search instead. Results are cached in memory: a
title's providers change slowly, and a run shows at most a dozen titles.
"""
import time

import httpx

from . import config

API = "https://api.themoviedb.org/3"
TTL_S = 6 * 3600
TRANSPORT: httpx.AsyncBaseTransport | None = None  # tests replace the network
_cache: dict[tuple[str, str], tuple[float, dict]] = {}


def _params() -> dict:
    return {"api_key": config.TMDB_API_KEY}


async def providers(imdb: str, country: str) -> dict:
    """{"link": TMDB page, "stream": [names], "rent": [names], "buy": [names]} for one country."""
    key = (imdb, country)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < TTL_S:
        return hit[1]
    out: dict = {"link": None, "stream": [], "rent": [], "buy": []}
    async with httpx.AsyncClient(timeout=8, transport=TRANSPORT) as client:
        found = (await client.get(f"{API}/find/{imdb}", params={**_params(), "external_source": "imdb_id"})).json()
        for kind, field in (("movie", "movie_results"), ("tv", "tv_results")):
            if found.get(field):
                tmdb_id = found[field][0]["id"]
                data = (await client.get(f"{API}/{kind}/{tmdb_id}/watch/providers", params=_params())).json()
                region = (data.get("results") or {}).get(country) or {}
                out = {"link": region.get("link"),
                       "stream": [p["provider_name"] for p in region.get("flatrate", [])][:4],
                       "rent": [p["provider_name"] for p in region.get("rent", [])][:3],
                       "buy": [p["provider_name"] for p in region.get("buy", [])][:3]}
                break
    _cache[key] = (time.monotonic(), out)
    return out
