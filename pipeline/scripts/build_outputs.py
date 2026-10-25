"""Build the committed data files from the cached lemma counts.

Writes:
  data/frequency_es.tsv   rank, lemma, titles (contextual diversity), count, main POS
  data/catalog_es.json    one row per title with its coverage curve
  data/vocab_items_es.json  items for the yes/no vocabulary check
  data/spanish_originals.json, data/spanish_names_es.json  Spanish-original ids and titles
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comprende_pipeline.config import CACHE_DIR, DATA_DIR  # noqa: E402
from comprende_pipeline.lexicon import normalize_counts, normalize_lemma  # noqa: E402
from comprende_pipeline.coverage import GRID, coverage_curve, frequency_ranks, vocab_needed  # noqa: E402
from comprende_pipeline.vocab_test import build_items  # noqa: E402
from comprende_pipeline.pace import bands, words_per_minute  # noqa: E402
from comprende_pipeline.wikipedia import is_spanish_language  # noqa: E402

FREQ_ROWS_KEPT = 25000


def main():
    titles = {t["imdb"]: t for t in json.loads((DATA_DIR / "titles_es.json").read_text(encoding="utf-8"))}
    # Titles Wikidata calls Spanish but whose English Wikipedia infobox lists another main language
    # (Extinction, White Lines): see scripts/check_wikipedia.py. They stay in the word-frequency counts
    # (their Spanish subtitles are still Spanish text, and the word check must not change), but are not
    # measured titles and are never recommended.
    spanish = {i: t for i, t in titles.items() if is_spanish_language(t.get("wp_languages") or [])}
    (DATA_DIR / "not_spanish_es.json").write_text(json.dumps(sorted(set(titles) - set(spanish)), separators=(",", ":")),
                                                  encoding="utf-8")
    # Spanish-original IMDb ids, used at run time to keep English co-productions out of recommendations.
    (DATA_DIR / "spanish_originals.json").write_text(json.dumps(sorted(spanish), separators=(",", ":")), encoding="utf-8")
    # Original Spanish titles, so Qloo's English names ("Cable Girls") can be shown as "Las chicas del cable".
    names = {i: t["title_es"] for i, t in sorted(spanish.items()) if t.get("title_es")}
    (DATA_DIR / "spanish_names_es.json").write_text(json.dumps(names, ensure_ascii=False, separators=(",", ":")),
                                                    encoding="utf-8")
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((CACHE_DIR / "lemmas").glob("*.json"))]
    records = [r for r in records if r["imdb"] in titles]
    print(f"{len(records)} lemmatised titles")
    # Repair lemmas the tagger left inflected or with attached pronouns ("déjalo" -> "dejar").
    for r in records:
        r["lemmas"] = normalize_counts(r["lemmas"])
        pos = {}
        for key, c in r["pos"].items():
            lemma, p = key.rsplit("|", 1)
            k = f"{normalize_lemma(lemma)}|{p}"
            pos[k] = pos.get(k, 0) + c
        r["pos"] = pos

    rows = frequency_ranks(records)[:FREQ_ROWS_KEPT]
    rank = {lemma: i for i, (lemma, _, _) in enumerate(rows, 1)}

    pos_counts: dict[str, Counter] = {}
    forms: set[str] = set()
    for r in records:
        for key, c in r["pos"].items():
            lemma, pos = key.rsplit("|", 1)
            if lemma in rank:
                pos_counts.setdefault(lemma, Counter())[pos] += c
        forms.update(r["forms"])
    main_pos = {lemma: c.most_common(1)[0][0] for lemma, c in pos_counts.items()}

    with open(DATA_DIR / "frequency_es.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write("rank\tlemma\ttitles\tcount\tpos\n")
        for i, (lemma, cd, count) in enumerate(rows, 1):
            f.write(f"{i}\t{lemma}\t{cd}\t{count}\t{main_pos.get(lemma, '')}\n")

    catalog = []
    for r in records:
        if r["imdb"] not in spanish:
            continue
        t = titles[r["imdb"]]
        curve = coverage_curve(r["lemmas"], r["marginal"], r["tokens"], rank)
        catalog.append({
            "imdb": t["imdb"],
            "wikidata": t["wikidata"],
            "type": t["type"],
            "title_es": t.get("title_es"),
            "title_en": t.get("title_en"),
            "year": t.get("year"),
            "countries": t.get("countries", []),
            "sitelinks": t["sitelinks"],
            "tokens": r["tokens"],
            "words_per_minute": words_per_minute(r["tokens"], (r.get("meta") or {}).get("duration"), t["type"]),
            "distinct_lemmas": len(r["lemmas"]),
            "vocab_for_95": vocab_needed(curve, 0.95),
            "vocab_for_98": vocab_needed(curve, 0.98),
            "coverage": curve,
            "source_file": r["source_file"],
        })
    catalog.sort(key=lambda c: -c["sitelinks"])
    pace_bands = bands([c["words_per_minute"] for c in catalog if c["words_per_minute"] is not None])
    (DATA_DIR / "catalog_es.json").write_text(
        json.dumps({"grid": GRID, "pace_bands": pace_bands, "titles": catalog}, ensure_ascii=False,
                   separators=(",", ":")), encoding="utf-8"
    )
    print(f"dialogue density for {sum(c['words_per_minute'] is not None for c in catalog)} titles, bands {pace_bands}")

    import simplemma

    def is_dictionary_word(w: str) -> bool:
        """A real item must be a dictionary base form; a pseudoword must match no Spanish form."""
        plain = w.translate(str.maketrans("áéíóú", "aeiou"))
        return simplemma.is_known(w, lang="es") or simplemma.is_known(plain, lang="es")

    def is_base_form(w: str) -> bool:
        return is_dictionary_word(w) and normalize_lemma(w) == w

    # Real items (ranked lemmas) must be base forms; generated pseudowords must match no Spanish word.
    items = build_items(rows, main_pos, forms,
                        is_dictionary_word=lambda w: is_base_form(w) if w in rank else is_dictionary_word(w))
    (DATA_DIR / "vocab_items_es.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"frequency rows {len(rows)}, catalog {len(catalog)}, vocab items {len(items['items'])}")


if __name__ == "__main__":
    main()
