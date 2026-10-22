"""Match free-text titles (as an LLM writes them) to Wikidata items, and classify each one.

Classes:
  spanish_original    in our Spanish-original list (data/titles_es.json)
  measured            spanish_original and in the coverage catalog (subset of the above)
  not_spanish         a real film/series on Wikidata whose original language is not Spanish
  unverified          no matching film or series found on Wikidata (possible invention; read by hand)
"""
import json
import re
import sys
import time
import unicodedata
from functools import lru_cache
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from comprende_pipeline.config import USER_AGENT  # noqa: E402
from comprende_pipeline.wikidata import is_spanish_original  # noqa: E402

FILM_OR_SERIES = {"Q11424", "Q5398426", "Q24856", "Q506240", "Q202866", "Q1259759", "Q21191270", "Q63952888"}


def norm(title: str) -> str:
    t = unicodedata.normalize("NFKD", title.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"[^a-z0-9n ]+", " ", t)
    t = t.strip()  # leading articles kept: stripping them matched Pixar "Coco" to the Spanish "El coco"
    return re.sub(r"\s+", " ", t).strip()


@lru_cache(maxsize=1)
def local_index():
    titles = json.loads((ROOT / "data" / "titles_es.json").read_text(encoding="utf-8"))
    cat = {t["imdb"] for t in json.loads((ROOT / "data" / "catalog_es.json").read_text(encoding="utf-8"))["titles"]}
    idx: dict[str, list[dict]] = {}
    for t in titles:
        for label in (t.get("title_es"), t.get("title_en")):
            if label:
                idx.setdefault(norm(label), []).append(t)
    return idx, cat


def _pick(rows: list[dict], year: int | None) -> dict | None:
    if year:
        close = [r for r in rows if r.get("year") and abs(r["year"] - year) <= 1]
        if close:
            return max(close, key=lambda r: r["sitelinks"])
        undated = [r for r in rows if not r.get("year")]  # many series carry no date on Wikidata
        return max(undated, key=lambda r: r["sitelinks"]) if undated else None
    return max(rows, key=lambda r: r["sitelinks"]) if rows else None


@lru_cache(maxsize=None)
def _wikidata_lookup(title: str) -> list[dict]:
    """Search Wikidata (Spanish and English labels) for films/series with this title; return their
    original languages and years."""
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    ids: list[str] = []
    for lang in ("es", "en"):
        for h in s.get("https://www.wikidata.org/w/api.php", params={
                "action": "wbsearchentities", "search": title, "language": lang, "uselang": lang,
                "type": "item", "limit": 25, "format": "json"}, timeout=30).json().get("search", []):
            if h["id"] not in ids and norm(h.get("label", "")) == norm(title):
                ids.append(h["id"])
    ids = ids[:40]
    if not ids:
        return []
    ents = s.get("https://www.wikidata.org/w/api.php", params={
        "action": "wbgetentities", "ids": "|".join(ids), "props": "claims", "format": "json"},
        timeout=30).json().get("entities", {})
    out = []
    for q in ids:
        claims = ents.get(q, {}).get("claims", {})
        kinds = {c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P31", [])}
        imdb = [c["mainsnak"].get("datavalue", {}).get("value", "") for c in claims.get("P345", [])]
        # An IMDb title id (tt...) marks a film or series whatever its exact Wikidata class.
        if not (kinds & FILM_OR_SERIES or any(str(i).startswith("tt") for i in imdb)):
            continue
        langs = [c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P364", [])]
        years = []
        for prop in ("P577", "P580"):
            for c in claims.get(prop, []):
                t = c["mainsnak"].get("datavalue", {}).get("value", {}).get("time", "")
                if len(t) > 5 and t[1:5].isdigit():
                    years.append(int(t[1:5]))
        out.append({"wikidata": q, "languages_q": [x for x in langs if x], "year": min(years) if years else None})
    time.sleep(0.2)
    return out


LANG_Q = {"Q1321": "es", "Q1860": "en", "Q7026": "ca", "Q9307": "gl", "Q8752": "eu", "Q397": "la"}


def classify(title: str, year: int | None = None) -> dict:
    idx, catalog = local_index()
    row = _pick(idx.get(norm(title), []), year)
    if row:
        return {"class": "measured" if row["imdb"] in catalog else "spanish_original",
                "imdb": row["imdb"], "wikidata": row["wikidata"], "matched": row.get("title_es") or row.get("title_en")}
    found = _wikidata_lookup(title)
    if year:  # prefer items released within a year of what the model said
        dated = [f for f in found if f["year"] and abs(f["year"] - year) <= 1]
        found = dated or [f for f in found if not f["year"]]
    if not found:
        return {"class": "unverified"}
    for f in found:
        langs = [LANG_Q.get(q, q) for q in f["languages_q"]]
        # Without country data for search hits: Spanish listed first and no English, or our usual rule.
        if langs and (langs[0] == "es" and "en" not in langs
                      or is_spanish_original({"languages": langs, "countries": []})):
            # Spanish-original on Wikidata but missing from our list (usually no IMDb id there).
            return {"class": "spanish_original", "wikidata": f["wikidata"], "matched": title}
    if all(not f["languages_q"] for f in found):
        return {"class": "unverified", "note": "found on Wikidata without an original language"}
    return {"class": "not_spanish", "wikidata": found[0]["wikidata"], "languages": found[0]["languages_q"]}
