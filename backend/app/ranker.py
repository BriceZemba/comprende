"""Taste x comprehension ranking. Deterministic: every number shown to the learner comes
from Qloo (affinity) or from the subtitle pipeline (coverage), never from the language model."""
import sys
from dataclasses import dataclass, field

from . import config
from .catalog import Measured

sys.path.insert(0, str(config.REPO_ROOT / "pipeline"))
from comprende_pipeline.coverage import GRID  # noqa: E402

BUCKET_ORDER = ["watch_now", "stretch", "later", "unmeasured"]


@dataclass
class Candidate:
    qloo_id: str | None
    name: str
    kind: str  # film | series
    year: int | None = None
    image: str | None = None
    description: str | None = None
    affinity: float | None = None
    popularity: float | None = None
    because: list[str] = field(default_factory=list)  # names of the learner's favourites that drove the pick
    tags: list[str] = field(default_factory=list)  # typed Qloo tags (genre, theme...), for the explainer
    traits: dict = field(default_factory=dict)  # Qloo's genre / themes / tone descriptions, for the explainer
    pace: tuple = (None, None)  # (words per minute, light|average|dense), see Catalog.pace
    measured: Measured | None = None


def _bucket(fit: str | None) -> str:
    return {"comfortable": "watch_now", "watchable": "watch_now", "stretch": "stretch", "later": "later"}.get(
        fit or "", "unmeasured")


def _lift(c: Candidate, typical: float | None) -> float | None:
    """How much more this title fits this learner than it fits a typical taste. Qloo gives some
    titles a high affinity for almost everyone; ranking by lift keeps lists personal."""
    if c.affinity is None:
        return None
    base = c.measured.taste_baseline if c.measured and c.measured.taste_baseline is not None else typical
    return round(c.affinity - base, 4) if base is not None else None


def rank(candidates: list[Candidate], vocab_size: float, per_bucket: int = 6) -> dict:
    """Group candidates by how much of the dialogue the learner can follow, most personal taste match first."""
    bases = [c.measured.taste_baseline for c in candidates if c.measured and c.measured.taste_baseline is not None]
    typical = sum(bases) / len(bases) if bases else None
    seen, picks = set(), []
    for c in candidates:
        key = c.measured.imdb if c.measured else (c.qloo_id or c.name.lower())
        if key in seen:
            continue
        seen.add(key)
        cov = c.measured.coverage_for(vocab_size) if c.measured else None
        fit = c.measured.fit_for(vocab_size) if c.measured else None
        need = c.measured.vocab_for_95 if c.measured else None
        picks.append({
            "qloo_id": c.qloo_id,
            "imdb": c.measured.imdb if c.measured else None,
            "name": (c.measured.title_es if c.measured and c.measured.title_es else c.name),
            "name_en": c.measured.title_en if c.measured else None,
            "kind": c.kind,
            "year": c.year or (c.measured.year if c.measured else None),
            "image": c.image,
            "description": c.description,
            "affinity": c.affinity,
            "lift": _lift(c, typical),
            "popularity": c.popularity,
            "because": c.because,
            "coverage": round(cov, 4) if cov is not None else None,
            "fit": fit,
            "vocab_for_95": need,
            "words_per_minute": (c.pace[0] or (c.measured.words_per_minute if c.measured else None)),
            "dialogue": (c.pace[1] or (c.measured.dialogue if c.measured else None)),
            "words_to_go": max(0, int(need - vocab_size)) if need else None,
            "bucket": _bucket(fit),
            "_curve": c.measured.coverage if c.measured else None,
        })

    def taste(p):
        key = p["lift"] if p["lift"] is not None else (p["affinity"] - 1 if p["affinity"] is not None else -9)
        return (key, p["affinity"] or 0)

    # Every measured candidate with a taste score goes on the map; the browser recomputes coverage
    # from the stored curve as the learner moves the vocabulary slider.
    taste_map = [{"key": p["imdb"], "name": p["name"], "kind": p["kind"], "year": p["year"],
                  "affinity": p["affinity"], "lift": p["lift"], "because": p["because"], "curve": p["_curve"]}
                 for p in picks if p["_curve"] is not None and p["affinity"] is not None]
    for p in picks:
        p.pop("_curve")
    buckets = {b: sorted([p for p in picks if p["bucket"] == b], key=taste, reverse=True)[:per_bucket]
               for b in BUCKET_ORDER}
    # The title the learner would most love but cannot follow yet: the agent holds it back on purpose.
    # Only when it is a genuinely strong match (affinity at or above the median of all candidates).
    later = [p for p in picks if p["bucket"] == "later"]
    held_back = max(later, key=taste) if later else None
    keys = sorted(taste(p) for p in picks)
    if held_back and keys and taste(held_back) < keys[len(keys) // 2]:
        held_back = None
    measured = [p for p in picks if p["coverage"] is not None]
    return {
        "vocab_size": int(vocab_size),
        "buckets": buckets,
        "held_back": held_back,
        "counts": {b: sum(1 for p in picks if p["bucket"] == b) for b in BUCKET_ORDER},
        "measured_share": round(len(measured) / len(picks), 3) if picks else 0.0,
        "map": {"grid": GRID, "titles": taste_map},
    }
