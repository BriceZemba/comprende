"""Everything to run once QLOO_API_KEY is in .env, in order, stopping at the first failure.

    python scripts/key_day.py

1. Live checks against the Qloo API (backend/scripts/qloo_spike.py)
2. Map measured titles to Qloo entities (backend/scripts/build_qloo_map.py -> data/qloo_map_es.json)
3. Run Comprende on the 20 evaluation profiles (eval/run_comprende.py)
4. Re-check titles and rebuild the evaluation report (eval/reclassify.py, eval/metrics.py)

Then commit data/qloo_map_es.json and eval/results/, add QLOO_API_KEY to the Vercel API project
and redeploy (see DEPLOY.md).
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ("Live Qloo checks", ["backend/scripts/qloo_spike.py"]),
    ("Map catalog to Qloo", ["backend/scripts/build_qloo_map.py"]),
    ("Comprende on the evaluation profiles", ["eval/run_comprende.py"]),
    ("Re-check Comprende titles", ["eval/reclassify.py", "comprende"]),
    ("Evaluation report", ["eval/metrics.py"]),
]


def key_present() -> bool:
    env = ROOT / ".env"
    if os.environ.get("QLOO_API_KEY"):
        return True
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("QLOO_API_KEY=") and line.split("=", 1)[1].strip():
                return True
    return False


def main():
    if not key_present():
        sys.exit("QLOO_API_KEY is not set in .env: add it first.")
    for i, (label, args) in enumerate(STEPS, 1):
        print(f"\n=== {i}/{len(STEPS)} {label} ===", flush=True)
        result = subprocess.run([sys.executable, *args], cwd=ROOT)
        out = (ROOT / "backend" / "tests" / "fixtures" / "live")
        if result.returncode != 0:
            sys.exit(f"Step {i} failed ({label}); fix it before continuing.")
        if i == 1 and not any(out.glob("*.json")):
            sys.exit("The live check saved no responses: read its output above before mapping the catalog.")
    print("\nDone. Next: commit data/qloo_map_es.json and eval/results/, then set QLOO_API_KEY on Vercel (DEPLOY.md).")


if __name__ == "__main__":
    main()
