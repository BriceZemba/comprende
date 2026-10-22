"""Comprende on the same 20 profiles. Uses the fixed plan (Qloo + subtitle coverage, no language
model), so the comparison with the LLM-only baseline isolates what Qloo and the coverage data add.

    python eval/run_comprende.py          # needs QLOO_API_KEY; writes eval/results/comprende.json
"""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config  # noqa: E402
from app.agent import ComprendeAgent  # noqa: E402
from app.catalog import load_catalog  # noqa: E402
from app.qloo import QlooClient  # noqa: E402
from titles import classify  # noqa: E402

ORDER = ["watch_now", "stretch", "unmeasured", "later"]  # the order the app shows them


async def main():
    config.GEMINI_API_KEY = ""  # fixed plan only
    profiles = json.loads((Path(__file__).parent / "profiles.json").read_text(encoding="utf-8"))["profiles"]
    q = QlooClient()

    async def emit(_):
        return None

    out = []
    try:
        for p in profiles:
            res = await ComprendeAgent(q, load_catalog(), emit).run(", ".join(p["favourites"]), {}, p["vocab_size"])
            picks = [x for b in ORDER for x in res["buckets"][b]][:10]
            titles = []
            for x in picks:
                t = {"title": x["name"], "year": x["year"], "kind": x["kind"], "affinity": x["affinity"]}
                t.update({"class": "measured", "imdb": x["imdb"], "matched": x["name"]} if x["imdb"]
                         else classify(x["name"], x["year"]))
                titles.append(t)
            out.append({"id": p["id"], "model": None, "favourites_resolved": list(res["favourites"].values()),
                        "titles": titles})
            print(p["id"], [t["title"] for t in titles][:4], flush=True)
    finally:
        await q.aclose()
    path = Path(__file__).parent / "results" / "comprende.json"
    path.write_text(json.dumps({"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "qloo_calls": q.calls, "results": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {path}; live Qloo calls {q.calls}")


if __name__ == "__main__":
    asyncio.run(main())
