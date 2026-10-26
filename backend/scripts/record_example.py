"""Record one real run of the home-page example, so judges and visitors can replay it without spending
the free model quota of the hosted demo.

    python backend/scripts/record_example.py

Runs the agent exactly as the app does (Gemini plans, Qloo answers, subtitles rank, the explainer writes
the reasons) for the example favourites at ~3,000 words, and writes data/example_run.json: the events in
order with their timing, the result, the reasons and the date. The web app labels the replay as a
recorded run with that date; a learner's own search always runs live. Rerun before a demo to refresh it.
"""
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.agent import ComprendeAgent  # noqa: E402
from app.catalog import load_catalog  # noqa: E402
from app.qloo import QlooClient  # noqa: E402

FAVOURITES = "Breaking Bad, Bad Bunny, The Legend of Zelda"
VOCAB = 3000
OUT = config.DATA_DIR / "example_run.json"


async def main():
    events: list[dict] = []
    t0 = time.monotonic()

    async def emit(e: dict):
        events.append({"at": round(time.monotonic() - t0, 2), "event": e})

    q = QlooClient(cache_dir=None)  # live answers, as in production
    try:
        agent = ComprendeAgent(q, load_catalog(), emit)
        result = await agent.run(FAVOURITES, {}, VOCAB)
        await emit({"type": "result", "result": result})
        explanations = await agent.explain_picks(result)
        if explanations:
            await emit({"type": "explanations", "explanations": explanations})
    finally:
        await q.aclose()
    if result["mode"] != "agent" or not explanations:
        sys.exit(f"not saved: mode={result['mode']}, reasons={len(explanations)}; the replay must show a full live run")
    OUT.write_text(json.dumps({"recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "favourites": FAVOURITES, "vocab": VOCAB, "events": events},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT}: {len(events)} events, model {result['model']}, {len(explanations)} reasons, "
          f"{events[-1]['at']} s")


if __name__ == "__main__":
    asyncio.run(main())
