"""Blind A/B lists for one learner test session: Comprende vs a language model alone, same inputs.

    python eval/blind_pair.py P1 3000 "Breaking Bad" "Rosalía" "FIFA 23"

Prints two lists labelled A and B in random order for the tester, and appends the hidden key
(which list is which) to eval/results/blind_key.csv. Show the tester only the printout.
"""
import asyncio
import csv
import json
import random
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
from run_llm_baseline import BASELINE_MODEL, PROMPT, ask  # noqa: E402

N = 5


async def comprende_list(favs: list[str], vocab: int) -> list[str]:
    key = config.GEMINI_API_KEY
    config.GEMINI_API_KEY = ""  # fixed plan: the comparison isolates Qloo + coverage
    q = QlooClient()

    async def emit(_):
        return None

    try:
        res = await ComprendeAgent(q, load_catalog(), emit).run(", ".join(favs), {}, vocab)
    finally:
        await q.aclose()
        config.GEMINI_API_KEY = key
    picks = [p for b in ("watch_now", "stretch") for p in res["buckets"][b]][:N]
    return [f"{p['name']} ({p['year']})" if p.get("year") else p["name"] for p in picks]


def llm_list(favs: list[str], vocab: int) -> list[str]:
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    titles = ask(client, BASELINE_MODEL, PROMPT.format(vocab=f"{vocab:,}", favs=", ".join(favs)))
    return [f"{t['title']} ({t['year']})" for t in titles[:N]]


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    tester, vocab, favs = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
    lists = {"comprende": asyncio.run(comprende_list(favs, vocab)), "llm_only": llm_list(favs, vocab)}
    order = random.sample(["comprende", "llm_only"], 2)
    for label, system in zip("AB", order):
        print(f"\nList {label}")
        for i, t in enumerate(lists[system], 1):
            print(f"  {i}. {t}")
    key = Path(__file__).parent / "results" / "blind_key.csv"
    new = not key.exists()
    with key.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["tester", "at", "vocab", "favourites", "list_A", "list_B", "A_titles", "B_titles"])
        w.writerow([tester, datetime.now(timezone.utc).isoformat(timespec="seconds"), vocab, " | ".join(favs),
                    order[0], order[1], json.dumps(lists[order[0]], ensure_ascii=False),
                    json.dumps(lists[order[1]], ensure_ascii=False)])


if __name__ == "__main__":
    main()
