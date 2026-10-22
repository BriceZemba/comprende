"""Measured titles: coverage curves from the pipeline, plus their Qloo entity ids."""
import json
import sys
from dataclasses import dataclass
from functools import lru_cache

from . import config

sys.path.insert(0, str(config.REPO_ROOT / "pipeline"))
from comprende_pipeline.coverage import coverage_at, fit_for  # noqa: E402


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

    def coverage_for(self, vocab_size: float) -> float:
        return coverage_at(self.coverage, vocab_size)

    def fit_for(self, vocab_size: float) -> str:
        return fit_for(self.coverage_for(vocab_size))


class Catalog:
    def __init__(self, titles: list[Measured]):
        self.titles = titles
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
            )
            for t in cat["titles"]
        ]
        return cls(titles)

    def match(self, qloo_id: str | None, imdb_ids: list[str] | None = None) -> Measured | None:
        if qloo_id and qloo_id in self.by_qloo:
            return self.by_qloo[qloo_id]
        for i in imdb_ids or []:
            if i in self.by_imdb:
                return self.by_imdb[i]
        return None


@lru_cache(maxsize=1)
def load_catalog() -> Catalog:
    return Catalog.from_files()
