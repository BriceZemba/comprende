"""Average Qloo affinity of every measured title across 10 reference tastes.

    python backend/scripts/build_taste_baseline.py

For some titles Qloo's affinity is high whatever the learner likes (popular Spanish series score
~0.85 for fans of Up and of The Lord of the Rings alike). Ranking by raw affinity would give
everyone the same list. The app ranks by lift instead: a title's affinity for this learner minus
its average affinity here. The reference tastes are deliberately different from the 20 evaluation
profiles in eval/profiles.json, so the evaluation is not tuned on itself.

Writes data/taste_baseline_es.json: {imdb: {"mean": float, "n": int}}.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.catalog import Catalog  # noqa: E402
from app.qloo import QlooClient  # noqa: E402

REFERENCE_TASTES = [
    ["The Simpsons", "Coldplay", "The Hunger Games"],
    ["Game of Thrones", "Drake", "Call of Duty"],
    ["Toy Story", "Billie Eilish", "Minecraft"],
    ["The Big Bang Theory", "Eminem", "Fortnite"],
    ["Titanic", "Celine Dion", "Twilight"],
    ["The Walking Dead", "Linkin Park", "Resident Evil"],
    ["How I Met Your Mother", "Rihanna", "The Sims"],
    ["Interstellar", "Pink Floyd", "Dune"],
    ["Gladiator", "AC/DC", "Assassin's Creed"],
    ["Amélie", "Norah Jones", "Little Women"],
]
OUT = config.DATA_DIR / "taste_baseline_es.json"


async def main():
    cat = Catalog.from_files()
    groups = {"urn:entity:movie": [t for t in cat.titles if t.qloo_id and t.kind == "film"],
              "urn:entity:tv_show": [t for t in cat.titles if t.qloo_id and t.kind == "series"]}
    sums: dict[str, list[float]] = {}
    q = QlooClient()
    try:
        for favs in REFERENCE_TASTES:
            ids = []
            for name in favs:
                hits = await q.search(name, take=1)
                if hits:
                    ids.append(hits[0].entity_id)
            for kind, titles in groups.items():
                for i in range(0, len(titles), 50):
                    chunk = titles[i:i + 50]
                    rows = await q.insights(**{"filter.type": kind, "signal.interests.entities": ids,
                                               "filter.results.entities": [t.qloo_id for t in chunk], "take": 50})
                    by_qloo = {t.qloo_id: t for t in chunk}
                    for r in rows:
                        if r.entity_id in by_qloo and r.affinity is not None:
                            sums.setdefault(by_qloo[r.entity_id].imdb, []).append(r.affinity)
            print(f"{favs[0]}: {len(sums)} titles scored so far, {q.calls} calls", flush=True)
    finally:
        await q.aclose()
    out = {k: {"mean": round(sum(v) / len(v), 4), "n": len(v)} for k, v in sums.items()}
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(out)} baselines; live calls {q.calls}")


if __name__ == "__main__":
    asyncio.run(main())
