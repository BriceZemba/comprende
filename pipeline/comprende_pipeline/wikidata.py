"""List films and TV series whose original language is Spanish, from Wikidata.

Subtitle text of a Spanish-original title is close to what the learner hears.
Spanish subtitles of an English film are a translation, so those are excluded.
"""
import time

import requests

from .config import USER_AGENT

SPARQL_URL = "https://query.wikidata.org/sparql"

# Q11424 film, Q5398426 television series, Q1321 Spanish, P345 IMDb id, P364 original language
BASE_QUERY = """
SELECT ?item ?imdb ?sitelinks WHERE {
  ?item wdt:P31 wd:%s; wdt:P364 wd:Q1321; wdt:P345 ?imdb; wikibase:sitelinks ?sitelinks.
}
"""

DETAIL_QUERY = """
SELECT ?item (MIN(YEAR(?date)) AS ?year) (SAMPLE(?es) AS ?title_es) (SAMPLE(?en) AS ?title_en)
       (GROUP_CONCAT(DISTINCT ?cc; separator=",") AS ?countries)
       (GROUP_CONCAT(DISTINCT ?langCode; separator=",") AS ?languages) WHERE {
  VALUES ?item { %s }
  OPTIONAL { ?item wdt:P577|wdt:P580 ?date }
  OPTIONAL { ?item wdt:P364/wdt:P218 ?langCode }
  OPTIONAL { ?item rdfs:label ?es FILTER(LANG(?es) = "es") }
  OPTIONAL { ?item rdfs:label ?en FILTER(LANG(?en) = "en") }
  OPTIONAL { ?item wdt:P495/wdt:P298 ?cc }
} GROUP BY ?item
"""

CLASSES = {"film": "Q11424", "series": "Q5398426"}


def _sparql(query: str) -> list[dict]:
    for attempt in range(4):
        r = requests.post(
            SPARQL_URL,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT},
            timeout=120,
        )
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()["results"]["bindings"]
    r.raise_for_status()
    return []


def fetch_spanish_titles(batch: int = 400) -> list[dict]:
    rows: dict[str, dict] = {}
    for kind, qid in CLASSES.items():
        for b in _sparql(BASE_QUERY % qid):
            imdb = b["imdb"]["value"]
            if not imdb.startswith("tt"):
                continue
            row = {
                "imdb": imdb,
                "wikidata": b["item"]["value"].rsplit("/", 1)[-1],
                "type": kind,
                "sitelinks": int(b["sitelinks"]["value"]),
            }
            # An item can carry several IMDb ids, and an id can sit on several items: keep the most linked.
            if imdb not in rows or row["sitelinks"] > rows[imdb]["sitelinks"]:
                rows[imdb] = row

    by_item: dict[str, list[dict]] = {}
    for row in rows.values():
        by_item.setdefault(row["wikidata"], []).append(row)
    items = list(by_item)
    for i in range(0, len(items), batch):
        values = " ".join(f"wd:{q}" for q in items[i : i + batch])
        for b in _sparql(DETAIL_QUERY % values):
            q = b["item"]["value"].rsplit("/", 1)[-1]
            for row in by_item.get(q, []):
                row["year"] = int(b["year"]["value"]) if "year" in b else None
                row["title_es"] = b.get("title_es", {}).get("value")
                row["title_en"] = b.get("title_en", {}).get("value")
                row["countries"] = [c for c in b.get("countries", {}).get("value", "").split(",") if c]
                row["languages"] = [c for c in b.get("languages", {}).get("value", "").split(",") if c]
    kept = [r for r in rows.values() if is_spanish_original(r)]
    return sorted(kept, key=lambda r: -r["sitelinks"])


# ISO 3166-1 alpha-3 codes of countries where Spanish is the main language of film and TV.
HISPANIC_COUNTRIES = {
    "ESP", "MEX", "ARG", "COL", "CHL", "PER", "VEN", "CUB", "URY", "PRY", "BOL", "ECU",
    "GTM", "HND", "SLV", "NIC", "CRI", "PAN", "DOM", "PRI", "GNQ",
}


# Languages that may share a Spanish production without making Spanish a translation.
IBERIAN_AND_INDIGENOUS = {"es", "ca", "gl", "eu", "la", "qu", "gn", "ay", "nah"}


def is_spanish_original(row: dict) -> bool:
    """Wikidata lists Spanish as an original language of some films that are not in Spanish
    (Predator, Il Postino, and even some with Spanish as the only listed language, such as
    Operation Finale). Keep a title only when a Spanish-speaking country produced it and its
    other original languages, if any, are Iberian or indigenous. Strict on purpose: a few
    genuine titles are lost (US Spanish-language productions), none are wrong."""
    langs = set(row.get("languages", []))
    hispanic = bool(set(row.get("countries", [])) & HISPANIC_COUNTRIES)
    return hispanic and langs <= IBERIAN_AND_INDIGENOUS
