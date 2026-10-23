"""Ablation: Comprende without Qloo. Same subtitle coverage and the same ranking into watch now /
stretch, but taste is replaced by general popularity (Wikidata sitelinks), so the favourites play
no part. Isolates what Qloo's taste graph adds.

    python eval/run_no_qloo.py      # no API calls; writes eval/results/no_qloo.json
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.catalog import Catalog  # noqa: E402
from app.ranker import Candidate, rank  # noqa: E402

ORDER = ["watch_now", "stretch", "unmeasured", "later"]


def main():
    cat = Catalog.from_files()
    for m in cat.titles:
        m.taste_baseline = None  # no Qloo data at all in this ablation
    titles = json.loads((ROOT / "data" / "catalog_es.json").read_text(encoding="utf-8"))["titles"]
    sitelinks = {t["imdb"]: t["sitelinks"] for t in titles}
    top = max(sitelinks.values())
    profiles = json.loads((Path(__file__).parent / "profiles.json").read_text(encoding="utf-8"))["profiles"]
    out = []
    for p in profiles:
        # Popularity stands in for taste: the same score for every learner.
        cands = [Candidate(m.qloo_id, m.title_es or m.title_en or m.imdb, m.kind, year=m.year,
                           affinity=sitelinks[m.imdb] / top, measured=m) for m in cat.titles if m.title_es]
        res = rank(cands, p["vocab_size"])
        picks = [x for b in ORDER for x in res["buckets"][b]][:10]
        out.append({"id": p["id"], "model": None, "titles": [
            {"title": x["name"], "year": x["year"], "kind": x["kind"], "class": "measured", "imdb": x["imdb"],
             "matched": x["name"]} for x in picks]})
    path = Path(__file__).parent / "results" / "no_qloo.json"
    path.write_text(json.dumps({"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "results": out},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
