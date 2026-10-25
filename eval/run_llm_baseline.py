"""LLM-only baseline: ask Gemini, with no Qloo and no subtitle data, for Spanish titles a learner
would love and understand. Same inputs Comprende gets: three favourites and a vocabulary size.

    python eval/run_llm_baseline.py            # writes eval/results/llm_only.json
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config  # noqa: E402
from titles import classify  # noqa: E402

# The baseline must be a strong model, not the app's fast planner: a weak baseline would flatter Comprende.
# It is pinned and never downgraded; when it is busy the run waits and retries.
BASELINE_MODEL = os.environ.get("BASELINE_MODEL", "gemini-3.5-flash")

PROMPT = """I am learning Spanish and know about {vocab} Spanish words.
I love: {favs}.
Recommend 10 films or TV series originally made in Spanish (Spanish is the original language of the
dialogue) that I would love given my taste and could follow at my level. Real titles only."""

SCHEMA = {
    "type": "object",
    "properties": {"titles": {"type": "array", "items": {"type": "object", "properties": {
        "title": {"type": "string"}, "year": {"type": "integer"}, "kind": {"type": "string", "enum": ["film", "series"]}},
        "required": ["title", "year", "kind"]}}},
    "required": ["titles"],
}


def ask(client, model: str, prompt: str) -> list[dict]:
    from google.genai import types

    resp = client.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=SCHEMA))
    return json.loads(resp.text)["titles"][:10]


def main():
    from google import genai
    from google.genai import errors

    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=90_000))
    profiles = json.loads((Path(__file__).parent / "profiles.json").read_text(encoding="utf-8"))["profiles"]
    # Saved after every profile, so an interrupted run resumes instead of starting over.
    partial = Path(__file__).parent / "results" / "llm_only.partial.json"
    out = json.loads(partial.read_text(encoding="utf-8")) if partial.exists() else []
    done = {r["id"] for r in out if r.get("model") == BASELINE_MODEL}
    out = [r for r in out if r["id"] in done]
    for p in profiles:
        if p["id"] in done:
            continue
        prompt = PROMPT.format(vocab=f"{p['vocab_size']:,}", favs=", ".join(p["favourites"]))
        for attempt in range(8):  # busy model: wait and retry, but never forever
            try:
                titles = ask(client, BASELINE_MODEL, prompt)
                break
            except errors.APIError as e:
                if e.code in (429, 500, 503, 504) and attempt < 7:
                    time.sleep(15 * (attempt + 1))
                    continue
                raise
        for t in titles:
            t.update(classify(t["title"], t.get("year")))
        out.append({"id": p["id"], "model": BASELINE_MODEL, "titles": titles})
        print(p["id"], BASELINE_MODEL, [f"{t['title']} [{t['class']}]" for t in titles][:4], flush=True)
        partial.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    path = Path(__file__).parent / "results" / "llm_only.json"
    path.write_text(json.dumps({"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "prompt": PROMPT, "results": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    partial.unlink(missing_ok=True)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
