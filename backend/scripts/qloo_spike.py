"""Go/no-go checks against the live Qloo API. Run once the key is in .env:

    python backend/scripts/qloo_spike.py

Answers, with saved responses in backend/tests/fixtures/live/:
  1. Does the key work on hackathon.api.qloo.com?
  2. How many catalog titles map to Qloo entities by IMDb id, and by Wikidata id?
  3. Do cross-domain favourites return Spanish-language films and series when
     filter.release_country is set to Spanish-speaking countries?
  4. Can filter.results.entities score our measured titles against a taste profile?
  5. Does feature.explainability return per-pick contributions?
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.qloo import QlooClient, QlooError  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "live"
SPANISH_COUNTRIES = ["Spain", "Mexico", "Argentina", "Colombia", "Chile", "Peru", "Uruguay", "Venezuela", "Cuba"]
FAVOURITES = [("Breaking Bad", "urn:entity:tv_show"), ("Radiohead", "urn:entity:artist"),
              ("Kafka on the Shore", "urn:entity:book")]


def save(name, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps([r.to_dict() for r in rows], ensure_ascii=False, indent=1),
                                      encoding="utf-8")


def show(rows, n=10):
    for r in rows[:n]:
        aff = f"{r.affinity:.3f}" if r.affinity is not None else "-"
        print(f"    {r.name} ({r.year}) {r.countries} aff={aff} pop={r.popularity}")


async def main():
    q = QlooClient(cache_dir=config.CACHE_DIR)
    catalog = json.loads((config.DATA_DIR / "catalog_es.json").read_text(encoding="utf-8"))["titles"]
    try:
        print("1. key check: /search 'La casa de papel'")
        rows = await q.search("La casa de papel", ["urn:entity:tv_show"], take=3)
        show(rows)
        save("search_casa_de_papel", rows)

        print("2. mapping catalog titles to Qloo entities (first 50)")
        sample = catalog[:50]
        by_imdb = await q.entities_by_external("imdb", [t["imdb"] for t in sample])
        by_wd = await q.entities_by_external("wikidata", [t["wikidata"] for t in sample])
        print(f"    by IMDb id: {len(by_imdb)}/50, by Wikidata id: {len(by_wd)}/50")
        save("entities_by_imdb", by_imdb)
        save("entities_by_wikidata", by_wd)

        print("3. favourites -> Spanish-language films and series")
        fav_ids = []
        for name, kind in FAVOURITES:
            hits = await q.search(name, [kind], take=1)
            if hits:
                fav_ids.append(hits[0].entity_id)
                print(f"    {name} -> {hits[0].name} {hits[0].entity_id}")
        for kind in ("urn:entity:movie", "urn:entity:tv_show"):
            recs = await q.insights(**{"filter.type": kind, "signal.interests.entities": fav_ids,
                                       "filter.release_country": SPANISH_COUNTRIES,
                                       "operator.filter.release_country": "union",
                                       "feature.explainability": True, "take": 30})
            print(f"    {kind}: {len(recs)} results")
            show(recs)
            save(f"insights_{kind.rsplit(':', 1)[-1]}_spanish", recs)
            print(f"    explainability present on {sum(1 for r in recs if r.explainability)}/{len(recs)}")

        print("4. scoring our measured titles with filter.results.entities")
        ids = [e.entity_id for e in by_imdb][:50]
        scored = await q.insights(**{"filter.type": "urn:entity:movie", "signal.interests.entities": fav_ids,
                                     "filter.results.entities": ids, "take": 50})
        print(f"    {len(scored)} of {len(ids)} returned with affinity")
        show(sorted(scored, key=lambda r: -(r.affinity or 0)))
        save("insights_results_entities", scored)
        print(f"\nlive calls made: {q.calls}")
    except QlooError as e:
        print(f"\nQLOO ERROR {e.code} ({e.status}): {e.message}")
    finally:
        await q.aclose()


if __name__ == "__main__":
    asyncio.run(main())
