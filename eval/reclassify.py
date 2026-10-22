"""Re-run title classification on stored results (after improving titles.py) without asking the
recommender again.  python eval/reclassify.py llm_only"""
import json
import sys
from pathlib import Path

from titles import classify

KEEP = ("title", "year", "kind", "affinity")

name = sys.argv[1]
path = Path(__file__).parent / "results" / f"{name}.json"
run = json.loads(path.read_text(encoding="utf-8"))
for r in run["results"]:
    for i, t in enumerate(r["titles"]):
        if t.get("class") == "measured" and name == "comprende":
            continue  # Comprende's measured picks are matched by IMDb id, not by name
        r["titles"][i] = {**{k: t[k] for k in KEEP if k in t}, **classify(t["title"], t.get("year"))}
path.write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"reclassified {path}")
