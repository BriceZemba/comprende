"""Map every measured title to its Qloo entity by IMDb id.

    python backend/scripts/build_qloo_map.py

/entities?external.imdb.ids=... accepts up to 50 ids but does not say which result belongs to which
id. Within a batch, each result is matched to a title by year (±1) and name (Spanish or English
title); only titles left unmatched are looked up one id at a time, so no mapping is guessed.
Writes data/qloo_map_es.json: {imdb: {"entity_id", "name", "via"}}.
"""
import asyncio
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.qloo import QlooClient  # noqa: E402

OUT = config.DATA_DIR / "qloo_map_es.json"


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def match_batch(batch: list[dict], rows) -> dict[str, object]:
    found = {}
    for t in batch:
        names = {norm(t.get("title_es")), norm(t.get("title_en"))} - {""}
        cands = [r for r in rows if norm(r.name) in names
                 and (not t.get("year") or not r.year or abs(r.year - t["year"]) <= 1)]
        if len(cands) == 1:
            found[t["imdb"]] = cands[0]
    return found


async def main():
    titles = json.loads((config.DATA_DIR / "catalog_es.json").read_text(encoding="utf-8"))["titles"]
    mapping = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = [t for t in titles if t["imdb"] not in mapping]
    q = QlooClient()
    singles = 0
    try:
        for i in range(0, len(todo), 50):
            batch = todo[i:i + 50]
            rows = await q.entities_by_external("imdb", [t["imdb"] for t in batch])
            for imdb, r in match_batch(batch, rows).items():
                mapping[imdb] = {"entity_id": r.entity_id, "name": r.name, "via": "imdb-batch"}
            for t in batch:
                if t["imdb"] in mapping:
                    continue
                one = await q.entities_by_external("imdb", [t["imdb"]])
                singles += 1
                if len(one) == 1:
                    mapping[t["imdb"]] = {"entity_id": one[0].entity_id, "name": one[0].name, "via": "imdb-single"}
            print(f"{min(i + 50, len(todo))}/{len(todo)} checked, {len(mapping)} mapped, {singles} single lookups", flush=True)
    finally:
        await q.aclose()
        OUT.write_text(json.dumps(mapping, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"mapped {len(mapping)}/{len(titles)} titles; live calls {q.calls}")


if __name__ == "__main__":
    asyncio.run(main())
