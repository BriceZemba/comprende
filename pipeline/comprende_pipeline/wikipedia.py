"""Two checks Wikidata gets wrong, read from Wikipedia instead.

1. Original language. Wikidata lists Spanish as the only original language of some films shot in English
   (Extinction 2015, The Nun 2005, White Lines). The English Wikipedia infobox `language =` field is
   usually right, and lists the main language first.
2. Title casing. Wikidata Spanish labels are sometimes in English title case ("El Desorden Que Dejas") or
   carry stray punctuation ("Libertador,"). Spanish Wikipedia article titles follow RAE casing
   ("Que Dios nos perdone", "¡Bienvenido, Mister Marshall!").
"""
import json
import re
import time
import unicodedata

from .config import CACHE_DIR, USER_AGENT

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
ENWIKI_API = "https://en.wikipedia.org/w/api.php"
BATCH = 50

# Infobox language names, matched in the order they appear in the field.
LANGUAGES = {
    "spanish": "es", "castilian": "es", "english": "en", "catalan": "ca", "galician": "gl", "basque": "eu",
    "portuguese": "pt", "french": "fr", "italian": "it", "german": "de", "quechua": "qu", "guarani": "gn",
    "aymara": "ay", "nahuatl": "nah", "mapudungun": "arn", "maya": "myn", "yucatec": "myn", "wayuu": "guc",
    "russian": "ru", "japanese": "ja", "mandarin": "zh", "chinese": "zh", "arabic": "ar", "hebrew": "he",
    "romanian": "ro", "polish": "pl", "hungarian": "hu", "dutch": "nl", "swedish": "sv", "danish": "da",
    "korean": "ko", "hindi": "hi", "turkish": "tr", "greek": "el", "latin": "la", "sign language": "sgn",
}
PAREN = re.compile(r"\s*\((?:película|pelicula|serie|telenovela|miniserie|programa|film|cortometraje|documental)[^)]*\)$",
                   re.IGNORECASE)


def _get(url: str, params: dict) -> dict:
    import requests  # only the fetchers need it; the parsing helpers and their tests run without it

    params = {**params, "format": "json", "formatversion": "2"}
    for attempt in range(5):
        r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        if "error" in data:  # never cache an API error as "no data"
            raise RuntimeError(f"{url}: {data['error'].get('code')}: {data['error'].get('info')}")
        return data
    r.raise_for_status()
    return {}


def _cached(name: str, keys: list[str], fetch) -> dict:
    """Fetch only the keys not cached yet; the cache makes reruns free and reproducible."""
    path = CACHE_DIR / "wikipedia" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    todo = [k for k in dict.fromkeys(keys) if k not in cache]
    for i in range(0, len(todo), BATCH):
        part = todo[i:i + BATCH]
        got = fetch(part)
        for k in part:
            cache[k] = got.get(k)
        if (i // BATCH) % 20 == 0:
            path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            print(f"  {name}: {min(i + BATCH, len(todo))}/{len(todo)}")
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return {k: cache.get(k) for k in keys}


def sitelinks(qids: list[str]) -> dict[str, dict | None]:
    """Spanish and English Wikipedia article titles per Wikidata item."""
    def fetch(part):
        data = _get(WIKIDATA_API, {"action": "wbgetentities", "ids": "|".join(part), "props": "sitelinks",
                                   "sitefilter": "eswiki|enwiki"})
        out = {}
        for q, e in (data.get("entities") or {}).items():
            links = e.get("sitelinks") or {}
            out[q] = {site: links[site]["title"] for site in ("eswiki", "enwiki") if site in links}
        return out
    return _cached("sitelinks", qids, fetch)


def infobox_wikitext(titles: list[str]) -> dict[str, str | None]:
    """Lead section (where the infobox lives) of English Wikipedia articles."""
    def fetch(part):
        data = _get(ENWIKI_API, {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                                 "rvsection": "0", "titles": "|".join(part), "redirects": "1"})
        q = data.get("query") or {}
        alias = {n["to"]: n["from"] for n in (q.get("normalized") or []) + (q.get("redirects") or [])}
        out = {}
        for page in q.get("pages") or []:
            revs = page.get("revisions") or []
            text = revs[0]["slots"]["main"]["content"] if revs else None
            title = page.get("title")
            out[alias.get(title, title)] = text
        return out
    return _cached("enwiki_lead", titles, fetch)


def infobox_languages(wikitext: str | None) -> list[str]:
    """Language codes from the infobox `language =` field, in the order listed (main language first)."""
    if not wikitext:
        return []
    m = re.search(r"^\s*\|\s*language\s*=(.*?)(?=^\s*\||^\s*\}\})", wikitext, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    value = re.sub(r"<!--.*?-->|<ref[^>]*/>|<ref.*?</ref>", " ", m.group(1), flags=re.DOTALL).lower()
    found: list[tuple[int, str]] = []
    for name, code in LANGUAGES.items():
        for hit in re.finditer(rf"\b{re.escape(name)}\b", value):
            found.append((hit.start(), code))
    seen: list[str] = []
    for _, code in sorted(found):
        if code not in seen:
            seen.append(code)
    return seen


def is_spanish_language(languages: list[str]) -> bool:
    """Keep a title unless its infobox leaves Spanish out or lists English first (Extinction: English;
    White Lines: English, Spanish). Other orders are kept: editors often list bilingual Spanish-Catalan or
    Spanish-indigenous films in either order. No language field means no evidence: keep."""
    return not languages or ("es" in languages and languages[0] != "en")


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"[^\w]+", "", "".join(c for c in s if not unicodedata.combining(c)))


def spanish_title(label: str | None, eswiki: str | None) -> str | None:
    """The Spanish Wikipedia title when it is the same title as the Wikidata label up to case,
    accents and punctuation (so its RAE casing and ¡! can be used); otherwise the label, tidied."""
    tidy = re.sub(r"[\s,;:]+$", "", label).strip() if label else label
    if eswiki:
        page = PAREN.sub("", eswiki).strip()
        # Some article titles keep a series' official Title Case ("La Reina del Flow"): take the article's
        # form only if it adds at most one capital (a proper noun, as in "Que Dios nos perdone").
        if tidy and _fold(page) == _fold(tidy) and _capitals(page) - _capitals(tidy) <= 1:
            return page
    return tidy


def _capitals(title: str) -> int:
    """Capitalised words after the first one."""
    return sum(1 for w in title.split()[1:] if w[:1].isupper())
