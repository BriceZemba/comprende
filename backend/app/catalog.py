"""Measured titles: coverage curves from the pipeline, plus their Qloo entity ids."""
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from . import config

sys.path.insert(0, str(config.REPO_ROOT / "pipeline"))
from comprende_pipeline.coverage import coverage_at, fit_for  # noqa: E402
from comprende_pipeline.pace import level as pace_level, words_per_minute  # noqa: E402


@dataclass
class Measured:
    imdb: str
    wikidata: str
    kind: str  # film | series
    title_es: str | None
    title_en: str | None
    year: int | None
    countries: list[str]
    coverage: list[float]
    vocab_for_95: int | None
    vocab_for_98: int | None
    qloo_id: str | None = None
    tokens: int = 0  # running words in the subtitle file
    words_per_minute: int | None = None  # dialogue density, films with reliable metadata only (pipeline/pace.py)
    dialogue: str | None = None  # light | average | dense, by thirds of the measured films
    taste_baseline: float | None = None  # mean Qloo affinity across reference tastes (see build_taste_baseline.py)
    sitelinks: int = 0  # Wikipedia editions with an article on it: how well known the title is

    def coverage_for(self, vocab_size: float) -> float:
        return coverage_at(self.coverage, vocab_size)

    def fit_for(self, vocab_size: float) -> str:
        return fit_for(self.coverage_for(vocab_size))


# Country names as Qloo writes them in country_of_origin.
SPANISH_SPEAKING = {"Spain", "Mexico", "Argentina", "Colombia", "Chile", "Peru", "Uruguay", "Venezuela", "Cuba",
                    "Ecuador", "Bolivia", "Paraguay", "Guatemala", "Honduras", "El Salvador", "Nicaragua",
                    "Costa Rica", "Panama", "Dominican Republic", "Puerto Rico", "Equatorial Guinea"}


class Catalog:
    def __init__(self, titles: list[Measured], spanish_ids: set[str] | None = None,
                 spanish_names: dict[str, str] | None = None, not_spanish: set[str] | None = None):
        self.titles = titles
        self.spanish_ids = spanish_ids or set()
        self.pace_bands: list[float] = []
        self.not_spanish = not_spanish or set()  # Wikidata says Spanish, Wikipedia says another main language
        self.spanish_names = spanish_names or {}  # imdb id -> original Spanish title (Wikidata)
        self._spanish_titles = {t.lower(): t for t in self.spanish_names.values()}
        self.by_imdb = {t.imdb: t for t in titles}
        self.by_qloo = {t.qloo_id: t for t in titles if t.qloo_id}

    @classmethod
    def from_files(cls, data_dir=config.DATA_DIR) -> "Catalog":
        cat = json.loads((data_dir / "catalog_es.json").read_text(encoding="utf-8"))
        qmap_file = data_dir / "qloo_map_es.json"
        qmap = json.loads(qmap_file.read_text(encoding="utf-8")) if qmap_file.exists() else {}
        titles = [
            Measured(
                imdb=t["imdb"], wikidata=t["wikidata"], kind=t["type"], title_es=t.get("title_es"),
                title_en=t.get("title_en"), year=t.get("year"), countries=t.get("countries", []),
                coverage=t["coverage"], vocab_for_95=t.get("vocab_for_95"), vocab_for_98=t.get("vocab_for_98"),
                qloo_id=(qmap.get(t["imdb"]) or {}).get("entity_id"),
                tokens=t.get("tokens", 0),
                sitelinks=t.get("sitelinks") or 0,
                words_per_minute=t.get("words_per_minute"),
                dialogue=pace_level(t.get("words_per_minute"), cat.get("pace_bands") or []),
            )
            for t in cat["titles"]
        ]
        base_file = data_dir / "taste_baseline_es.json"
        base = json.loads(base_file.read_text(encoding="utf-8")) if base_file.exists() else {}
        for t in titles:
            if t.imdb in base:
                t.taste_baseline = base[t.imdb]["mean"]
        ids_file = data_dir / "spanish_originals.json"
        spanish_ids = set(json.loads(ids_file.read_text(encoding="utf-8"))) if ids_file.exists() else set()
        names_file = data_dir / "spanish_names_es.json"
        names = json.loads(names_file.read_text(encoding="utf-8")) if names_file.exists() else {}
        not_file = data_dir / "not_spanish_es.json"
        not_spanish = set(json.loads(not_file.read_text(encoding="utf-8"))) if not_file.exists() else set()
        catalog = cls(titles, spanish_ids, names, not_spanish)
        catalog.pace_bands = cat.get("pace_bands") or []
        return catalog

    def pace(self, m: "Measured", qloo_minutes: float | None) -> tuple[int | None, str | None]:
        """Dialogue density from the subtitle metadata, or else from Qloo's running time, same rule."""
        wpm = m.words_per_minute or words_per_minute(m.tokens, qloo_minutes, m.kind)
        return wpm, pace_level(wpm, self.pace_bands)

    def spanish_name(self, imdb_ids: list[str], akas_es: list[str] | None = None) -> str | None:
        """Qloo names titles in English ("Cable Girls"); learners should see "Las chicas del cable".
        By IMDb id, or else by a Spanish alternate title that is a known Spanish-original title (so an
        American favourite is not renamed "El origen")."""
        by_id = next((self.spanish_names[i] for i in imdb_ids if i in self.spanish_names), None)
        return by_id or next((self._spanish_titles[a.lower()] for a in akas_es or [] if a.lower() in self._spanish_titles),
                             None)

    def is_spanish_original(self, imdb_ids: list[str], countries: list[str]) -> bool:
        """Qloo's release-country filter also returns co-productions in English (Enemy: Canada/Spain/France).
        Keep a title only if Wikidata lists it as Spanish-original, or every production country speaks Spanish.
        A title Wikipedia shows to be mainly in another language (White Lines) is dropped either way."""
        if any(i in self.not_spanish for i in imdb_ids):
            return False
        if any(i in self.spanish_ids or i in self.by_imdb for i in imdb_ids):
            return True
        return bool(countries) and all(c in SPANISH_SPEAKING for c in countries)

    def search(self, query: str, limit: int = 6) -> list[Measured]:
        """Titles whose Spanish or English name matches what the learner typed, ignoring case, accents and
        punctuation: exact names first, then names that start with it, then any word that does, then any
        other match, then names holding every typed word in any order; the best-known titles first within each."""
        q = _fold(query)
        if len(q) < 2:
            return []
        words = q.split()

        def rank_of(n: str) -> int:
            if n == q:
                return 0
            if n.startswith(q):
                return 1
            if f" {q}" in f" {n}":
                return 2
            if q in n:
                return 3
            name_words = n.split()
            if len(words) > 1 and all(any(w.startswith(x) for w in name_words) for x in words):
                return 4
            return 9

        scored = []
        for t in self.titles:
            names = [_fold(n) for n in (t.title_es, t.title_en) if n]
            rank = min(rank_of(n) for n in names) if names else 9
            if rank < 9:
                scored.append((rank, -t.sitelinks, t.title_es or t.title_en or "", t))
        return [s[-1] for s in sorted(scored, key=lambda s: s[:3])[:limit]]

    def match(self, qloo_id: str | None, imdb_ids: list[str] | None = None) -> Measured | None:
        if qloo_id and qloo_id in self.by_qloo:
            return self.by_qloo[qloo_id]
        for i in imdb_ids or []:
            if i in self.by_imdb:
                return self.by_imdb[i]
        return None


def _fold(text: str) -> str:
    """Lowercase, no accents, punctuation as spaces: "¿Qué pasó, Élite?" -> "que paso elite"."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


@lru_cache(maxsize=1)
def load_catalog() -> Catalog:
    return Catalog.from_files()
