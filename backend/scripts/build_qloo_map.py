"""Map every measured title to its Qloo entity, by IMDb id then by Wikidata id.

    python backend/scripts/build_qloo_map.py

Writes data/qloo_map_es.json: {imdb: {"entity_id", "name", "via"}}. Batches of 50 ids per
request; when a batch response does not say which id matched which entity, the batch is
retried one id at a time so no mapping is guessed.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.qloo import Entity, QlooClient  # noqa: E402

OUT = config.DATA_DIR / "qloo_map_es.json"


def _ids(e: Entity, source: str) -> set[str]:
    vals = e.external.get(source) or []
    if isinstance(vals, dict):
        vals = [vals]
    return {str(v.get("id")) for v in vals if isinstance(v, dict) and v.get("id")}


async def map_by(q: QlooClient, titles: list[dict], source: str, key: str, mapping: dict) -> None:
    todo = [t for t in titles if t["imdb"] not in mapping]
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        rows = await q.entities_by_external(source, [t[key] for t in batch])
        if all(_ids(r, source) for r in rows):
            for t in batch:
                hit = next((r for r in rows if t[key] in _ids(r, source)), None)
                if hit:
                    mapping[t["imdb"]] = {"entity_id": hit.entity_id, "name": hit.name, "via": source}
        else:
            for t in batch:
                one = await q.entities_by_external(source, [t[key]])
                if len(one) == 1:
                    mapping[t["imdb"]] = {"entity_id": one[0].entity_id, "name": one[0].name, "via": source}
        print(f"{source}: {min(i + 50, len(todo))}/{len(todo)} checked, {len(mapping)} mapped", flush=True)


async def main():
    titles = json.loads((config.DATA_DIR / "catalog_es.json").read_text(encoding="utf-8"))["titles"]
    mapping = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    q = QlooClient()
    try:
        await map_by(q, titles, "imdb", "imdb", mapping)
        await map_by(q, titles, "wikidata", "wikidata", mapping)
    finally:
        await q.aclose()
        OUT.write_text(json.dumps(mapping, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"mapped {len(mapping)}/{len(titles)} titles; live calls {q.calls}")


if __name__ == "__main__":
    asyncio.run(main())
