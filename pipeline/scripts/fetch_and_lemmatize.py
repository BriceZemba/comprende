"""Fetch one Spanish subtitle file per Spanish-original title and lemmatise it.

Usage: python scripts/fetch_and_lemmatize.py [--limit N] [--workers 8]
Reads data/titles_es.json, writes <cache>/lemmas/<imdb>.json (resumable).
Only lemma counts are kept; subtitle text is never written to the repository.
"""
import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comprende_pipeline.config import CACHE_DIR, DATA_DIR, OPUS_ES_URL, ensure_dirs  # noqa: E402
from comprende_pipeline.lexicon import lexicon_from_sentences, load_nlp  # noqa: E402
from comprende_pipeline.remote_zip import _session, fetch_member, load_index, members_by_imdb  # noqa: E402
from comprende_pipeline.subtitles import parse_opus_xml  # noqa: E402

MIN_SENTENCES = 150  # shorter files are usually trailers, fragments or broken uploads


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    ensure_dirs()
    titles = json.loads((DATA_DIR / "titles_es.json").read_text(encoding="utf-8"))
    groups = members_by_imdb(load_index(OPUS_ES_URL, CACHE_DIR / "es_v2024_index.pkl"))
    todo = [t for t in titles if t["imdb"] in groups]
    print(f"{len(titles)} titles, {len(todo)} with Spanish subtitles in the corpus", flush=True)
    if args.limit:
        todo = todo[: args.limit]
    out_dir = CACHE_DIR / "lemmas"
    todo = [
        t for t in todo
        if not (out_dir / f"{t['imdb']}.json").exists() and not (out_dir / f"{t['imdb']}.skip").exists()
    ]
    print(f"{len(todo)} to process", flush=True)

    local = threading.local()

    def download(t):
        # Several uploads exist per title; the largest is the least likely to be a fragment.
        name, offset, size = max(groups[t["imdb"]], key=lambda e: e[2])
        if not hasattr(local, "session"):
            local.session = _session()
        try:
            return t, name, parse_opus_xml(fetch_member(OPUS_ES_URL, offset, size, local.session))
        except Exception as exc:  # network or XML error: record and move on
            return t, name, exc

    nlp = load_nlp()
    start, done, skipped = time.time(), 0, 0
    with ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(download, t) for t in todo]
        for fut in as_completed(futures):
            t, name, result = fut.result()
            if isinstance(result, Exception) or len(result[0]) < MIN_SENTENCES:
                skipped += 1
                reason = repr(result) if isinstance(result, Exception) else f"{len(result[0])} sentences"
                (out_dir / f"{t['imdb']}.skip").write_text(reason, encoding="utf-8")
                continue
            sentences, meta = result
            lex = lexicon_from_sentences(nlp, sentences)
            record = {"imdb": t["imdb"], "source_file": name, "meta": meta, **lex.to_json()}
            (out_dir / f"{t['imdb']}.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            done += 1
            if done % 25 == 0:
                rate = done / (time.time() - start)
                print(f"{done} done, {skipped} skipped, {rate:.2f}/s", flush=True)
    print(f"finished: {done} done, {skipped} skipped in {time.time() - start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
