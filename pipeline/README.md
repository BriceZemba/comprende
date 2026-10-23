# Comprehension pipeline

Offline pipeline that measures how much of a Spanish film a learner can follow, from real subtitle text.

## What it produces (committed in `data/`)

| File | Contents |
|---|---|
| `titles_es.json` | Films and TV series whose original language is Spanish, from Wikidata (IMDb id, titles, year, countries, sitelinks) |
| `frequency_es.tsv` | Spanish lemma ranks built from the subtitles of those titles, ranked by the number of titles a lemma appears in |
| `catalog_es.json` | One row per measured title: coverage at each vocabulary size, and the vocabulary needed for 95% and 98% coverage |
| `vocab_items_es.json` | Items for the yes/no vocabulary check (real words by frequency band + pseudowords) |

Subtitle text is never committed: only counts derived from it.

## Method

1. **Titles.** Wikidata items that are films or TV series with Spanish as an original language, produced in a Spanish-speaking country, with any other original language Iberian or indigenous. Wikidata lists Spanish for some films that are not in Spanish (*Predator*, *Operation Finale*); their Spanish subtitles are a translation, not what you hear. The rule is strict on purpose: a few US Spanish-language productions are lost.
2. **Subtitles.** OPUS OpenSubtitles v2024, Spanish (Lison & Tiedemann 2016, data from [opensubtitles.org](https://www.opensubtitles.org/)). The 18 GB archive is not downloaded: its central directory is read once and each title's subtitle file is fetched by HTTP byte range. For each title the largest upload is used.
3. **Lemmas.** spaCy `es_core_news_sm`. Punctuation and numbers are ignored. Proper nouns and interjections count as known, as in coverage studies of film (Webb & Rodgers 2009). The tagger leaves some verbs inflected or with attached pronouns (*déjalo*, *acompañarte*, *quieras*); these are repaired with the dictionary-based lemmatiser simplemma, used only for forms its dictionary knows, after stripping clitic pronouns (*dímelo* → *decir*). Without this repair the median title appeared to need 4,500 lemmas for 95% coverage instead of 3,000. Cases are in `tests/test_lexicon.py`.
4. **Frequency.** Lemmas ranked by contextual diversity (how many titles use them), then by count (Adelman, Brown & Quesada 2006; Cuetos et al. 2011 for SUBTLEX-ESP).
5. **Coverage.** A learner who knows the V most frequent lemmas knows that share of a title's running words. Stored for V from 250 to 20,000. Thresholds: 95% for adequate comprehension, 98% for comfortable comprehension (Hu & Nation 2000; Nation 2006).
6. **Vocabulary check.** 48 real words (8 from each of 6 frequency bands up to rank 12,000) and 16 pseudowords. Real words must be dictionary base forms; pseudowords are generated from a character model and rejected if any Spanish form matches them. The final list was read by hand and 11 items removed (`REVIEWED_OUT` in `vocab_test.py`). Hit rates are corrected for guessing with the false-alarm rate (Meara & Buxton 1987) and scaled by band width.

## Validation

From `data/validation_es.md` (1,464 titles):

- The median title needs **3,000 lemmas for 95% coverage** (middle half: 2,500–4,000) and 8,000 for 98%. Webb & Rodgers (2009) found about 3,000 word families plus proper nouns give 95% coverage of English film dialogue, so the measure lands where published research predicts.
- Knowing 3,000 lemmas covers 95.1% of the words in the median title; 1,000 lemmas cover 89.8%.
- **A hypothesis that did not hold:** we expected animation and family titles to need fewer words than dramas. They need slightly more (94.1% vs 95.4% coverage at 3,000 lemmas; only 25 animated titles). We have not tested why.

## Known limits

- Lemmas are narrower than word families, so a learner who knows *comer* is not credited with *comida*: coverage estimates are conservative.
- Speech rate, accents, slang density and visual support also affect comprehension and are not measured.
- Coverage is computed from one subtitle upload per title; subtitles condense speech, so the real dialogue has more words.
- The part-of-speech tagger sometimes tags sentence-initial words as proper nouns, which counts them as known.
- Only titles present in the OPUS corpus can be measured. Others are shown as "not measured" rather than guessed.

## Run

```bash
pip install -r requirements.txt
python -m spacy download es_core_news_sm
python -c "from comprende_pipeline.wikidata import fetch_spanish_titles as f; import json; json.dump(f(), open('../data/titles_es.json','w',encoding='utf-8'), ensure_ascii=False)"
python scripts/fetch_and_lemmatize.py --workers 8
python scripts/build_outputs.py
python -m pytest -q tests
```

The subtitle index and per-title lemma counts are cached in `~/.cache/comprende` (override with `COMPRENDE_CACHE`).

## References

- Adelman, J. S., Brown, G. D. A., & Quesada, J. F. (2006). Contextual diversity, not word frequency, determines word-naming and lexical decision times. *Psychological Science*, 17(9).
- Cuetos, F., Glez-Nosti, M., Barbón, A., & Brysbaert, M. (2011). SUBTLEX-ESP: Spanish word frequencies based on film subtitles. *Psicológica*, 32.
- Hu, M., & Nation, I. S. P. (2000). Unknown vocabulary density and reading comprehension. *Reading in a Foreign Language*, 13(1).
- Lison, P., & Tiedemann, J. (2016). OpenSubtitles2016: Extracting large parallel corpora from movie and TV subtitles. *LREC 2016*.
- Barbaresi, A. (2023). simplemma: a simple multilingual lemmatizer for Python (v2.0). https://github.com/adbar/simplemma
- Meara, P., & Buxton, B. (1987). An alternative to multiple choice vocabulary tests. *Language Testing*, 4(2).
- Nation, I. S. P. (2006). How large a vocabulary is needed for reading and listening? *Canadian Modern Language Review*, 63(1).
- Webb, S., & Rodgers, M. P. H. (2009). The lexical coverage of movies. *Applied Linguistics*, 30(3).
