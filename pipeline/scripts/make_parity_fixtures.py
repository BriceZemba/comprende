"""Generate pipeline/fixtures/parity.json: inputs and Python outputs that the web app's
TypeScript port (web/lib/comprehension.ts) must reproduce exactly."""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comprende_pipeline.coverage import GRID, coverage_at, fit_for  # noqa: E402
from comprende_pipeline.vocab_test import BANDS, estimate_vocab  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "parity.json"


def main():
    rng = random.Random(42)
    items = []
    for lo, hi in BANDS:
        items += [{"word": f"w{lo}_{k}", "real": True, "band": [lo, hi]} for k in range(8)]
    items += [{"word": f"fake{k}", "real": False} for k in range(16)]

    vocab_cases = []
    for _ in range(200):
        skill, bluff = rng.uniform(0, 1), rng.uniform(0, 0.4)
        answers = {}
        for i in items:
            if i["real"]:
                p = max(0.0, min(1.0, skill * 1.4 - i["band"][0] / 12000))
            else:
                p = bluff
            if rng.random() < 0.9:  # leave some unanswered
                answers[i["word"]] = rng.random() < p
        vocab_cases.append({"answers": answers, "expected": estimate_vocab(items, answers)})

    coverage_cases = []
    for _ in range(200):
        steps = sorted(rng.uniform(0.6, 1.0) for _ in GRID)
        curve = [round(x, 4) for x in steps]
        v = rng.choice([0, 100, 250, 999, 1000, 1234.5, 5000, 15000, 20000, 30000, rng.uniform(0, 21000)])
        cov = coverage_at(curve, v)
        coverage_cases.append({"curve": curve, "vocab": v, "expected": cov, "fit": fit_for(cov)})

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"bands": BANDS, "grid": GRID, "items": items,
                               "vocab_cases": vocab_cases, "coverage_cases": coverage_cases}), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
