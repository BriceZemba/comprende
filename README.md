# Comprende

**Spanish films and series you'll love, at a level you'll understand.**

**Try it:** https://comprende.vercel.app · **Method and evidence:** https://comprende.vercel.app/method · Built for the Qloo Agentic Hackathon (2026)

![Comprende home page: an animated example goes from three favourites to a Spanish film you can follow and one held back for later](docs/home.png)

Learners are told to watch shows in Spanish. They pick something famous, get lost in the dialogue, and quit. Comprende starts from three things you love, in any domain (a show, an artist, a game):
- it uses the **Qloo** taste graph to find Spanish-language films and series with the same feel;
- it measures how much of each title's dialogue you would understand, from real subtitles;
- it ranks them so you start with what you'll enjoy **and** follow, and holds back the title you'd love most until you're ready.

## Try it in 60 seconds

1. Open https://comprende.vercel.app. **Try an example** replays a recorded real run in a few seconds.
2. For your own picks, give three favourites, choose which Spanish you want to hear (Spain, Latin America or both), and take the 64-word check or choose a level.
3. Watch the agent's steps live, then read your picks:
   - **Watch now:** at least 95% of the words known.
   - **A good stretch:** 90–95%.
   - One title **held back on purpose**.

   Each pick comes with a one-line reason, how much dialogue it has, and where to watch it in your country.
4. Drag the **vocabulary slider** on the map to see titles move from "later" to "watch now".
5. Save titles to **My list**. After a film, answer "Watched it?" and your level moves. The next visit tells you what came within reach.
6. Switch **EN / FR / ES** and light / dark in the header.

## How Qloo powers it

| Step | Qloo API | Why |
|---|---|---|
| Resolve favourites from any domain | `GET /search` (films, series, artists, games, books, podcasts) | "Breaking Bad", "Rosalía", "Zelda" become Qloo entities |
| Spanish-language films and series for your taste | `GET /v2/insights` with `filter.type`, `signal.interests.entities`, `filter.release_country` (Spanish-speaking countries) | Cross-domain taste becomes Spanish titles |
| The Spanish you want to hear | `filter.release_country` narrowed to Spain or to Latin America, at the learner's choice | Accents and words differ; a learner of Mexican Spanish gets Mexican and Argentine titles |
| Score the titles we measured | `GET /v2/insights` with `filter.results.entities` (parallel batches of 50) | A taste score for every title whose difficulty we know |
| Explain each pick | `feature.explainability`, plus Qloo's genre, themes and tone descriptions | "Because you like…" and the explainer's reason come from Qloo's data, not the model's memory |
| Map our catalog to Qloo | `GET /entities` with `external.imdb.ids`, `external.wikidata.ids` | Exact ids (1,438 of 1,464 titles), no fuzzy matching |
| Spanish-language music | `GET /v2/tags` and `GET /v2/insights` with `filter.tags`, kept to genres sung in Spanish | Listening practice from the same taste |
| Personal, not just popular | Mean affinity of each title over 10 reference tastes (`backend/scripts/build_taste_baseline.py`) | Ranking by lift (your affinity minus the typical one) |

**Two agents, and every number comes from Qloo or the subtitles, never from a language model.**
- **Planner** (Gemini with tool calling): decides the Qloo calls and runs them in parallel. A deterministic ranker orders the results.
- **Explainer:** writes one reason per pick in English, French and Spanish, only from Qloo's description of the title. Its output is checked before it is shown.
- **When the models fail:** if Gemini is down or out of quota, open models through OpenRouter take over (`OPENROUTER_API_KEY`). If no model answers, the same tools run as a fixed plan.

## Evidence

| Claim | Result | Where |
|---|---|---|
| Titles measured from real subtitles | 1,464 Spanish-original films and series, language checked against Wikidata and Wikipedia | `data/catalog_es.json` |
| The difficulty measure behaves as published research predicts | Median title needs 3,000 lemmas for 95% coverage (Webb & Rodgers 2009: about 3,000 word families plus proper nouns for English film) | `data/validation_es.md` |
| A hypothesis that did not hold | Animation and family titles are **not** easier than dramas (94.0% vs 95.4% coverage at 3,000 lemmas) | `data/validation_es.md` |
| A language model alone ignores level | Gemini with no Qloo and no subtitles, on 20 profiles: of its 88 measured picks, 61.4% followable at the learner's level, 14.8% below 90% coverage | `eval/results/report.md` |
| Qloo is what makes it personal | Same subtitle data without Qloo (popularity instead of taste): 8.0% distinct titles across 20 learners, list overlap 0.66. With Qloo: 68.5% distinct, overlap 0.03 | `eval/results/report.md` |
| Comprende vs. a language model, first five picks | 69.7% followable at the learner's level vs 60.0%; 0.0% far too hard (< 90%) vs 14.0%; 93.5% verified Spanish-original vs 86.5% | `eval/results/report.md` |
| Real people can use it | 9 testers (6 learning Spanish): none needed help, median 14 s to results, 4.0 of the first 5 picks they would watch, 9 of 9 explained "held back" correctly | user test sheet (not in the repo: testers' answers) |

**Reproduce:** `python pipeline/scripts/validate_catalog.py`, `python eval/run_llm_baseline.py`, `python eval/run_comprende.py`, `python eval/metrics.py`.

## Architecture

```mermaid
flowchart LR
  U[Learner] --> W[Next.js web app EN/FR/ES]
  W -->|stream of agent steps| A[FastAPI agent]
  A -->|plans tool calls| G[Gemini]
  A -.->|if Gemini fails| O[Open models via OpenRouter]
  A -->|search, insights, tags, entities| Q[(Qloo API)]
  A --> R[Ranker: taste x comprehension]
  R --> E[Explainer agent: one reason per pick]
  C[(Coverage catalog: 1,464 titles)] --> R
  P[Offline pipeline: Wikidata + Wikipedia titles, OPUS subtitles, lemmas] --> C
  W -->|where to watch| T[(TMDB, data by JustWatch)]
```

| Folder | What |
|---|---|
| `pipeline/` | Offline: Spanish-original titles (Wikidata, language checked on Wikipedia), subtitles (OPUS OpenSubtitles, fetched by byte range), lemmatisation with clitic repair, frequency list, coverage curves, dialogue density, vocabulary-check items |
| `backend/` | Qloo client (server-side key, cached), planner and explainer agents, model backups, ranker, API with server-sent events, recorded example |
| `web/` | Next.js app: favourites, word check, live agent steps, results, map, My list, welcome back, methods page, EN/FR/ES, installable |
| `eval/` | Fixed taste profiles, language-model baseline, Comprende runner, title verification, report |

## Run locally

```bash
cp .env.example .env            # QLOO_API_KEY and GEMINI_API_KEY; OPENROUTER_API_KEY and TMDB_API_KEY are optional
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --port 8000
cd web && npm install && npm run dev   # http://localhost:3000
```

**Tests** (CI runs them all):
- `python -m pytest -q pipeline/tests`
- `cd backend && python -m pytest -q tests`
- `node --experimental-strip-types web/lib/comprehension.parity.test.ts`: the web app's maths checked against the Python pipeline.
- `node --experimental-strip-types web/lib/profile.test.ts`

To refresh the home-page example before a demo: `python backend/scripts/record_example.py`.

## Limits

- **Coverage counts words, not speech rate, accents or slang.** As a rough guide to pace, films whose running time is known (from the subtitle metadata or from Qloo) also show their dialogue density: subtitle words per minute of running time, in thirds (under 60, 60–80, over 80). It is not speech rate, since silent scenes count in the minutes and subtitles condense speech. A learner can follow 95% of the words of a fast Andalusian thriller and still struggle.
- **Only titles in the open subtitle corpus are measured;** others are labelled "difficulty not measured", never guessed. Series are thin: the open corpus holds almost only films (40 of the 1,464 measured titles are series; we checked the corpus against IMDb's episode list and it contains no episode files of Spanish series). The next step is a licence with OpenSubtitles or with streaming platforms.
- **The word check is short** (64 items) and approximate. Spanish words that look like English or French ones (cognates, false friends) are left out because they can be recognised without knowing Spanish, so the estimate may be a little low for those learners.
- **The music lane depends on Qloo genre tags:** an artist must carry a genre sung in Spanish (reggaeton, cumbia, flamenco, Latin pop, Spanish rap…) and none sung in another language. Lyrics are not measured. Podcasts are left out because Qloo's "Spanish" podcast tags describe topics (Spanish history), not the language of the show.
- **Qloo's language filter is by release country,** which also returns co-productions in English. Titles are kept only if Wikidata lists them as Spanish-original or every production country is Spanish-speaking, and dropped when their English Wikipedia infobox leaves Spanish out or lists English first (52 titles). Titles without an English Wikipedia article are not checked this way, so a rare Catalan- or English-language title can still get through.
- **Qloo returned taste scores for 657 of our 1,438 Qloo-matched titles;** the others cannot be ranked by taste.
- **The reasons under each pick are generated text.** They are written only from Qloo's description of the title and checked before they are shown. Every number (coverage, vocabulary, dialogue density) comes from Qloo or the subtitles.
- **The hosted demo runs on free model quotas** (Gemini, with open models through OpenRouter as backup). When all of them are used up for the day, the same tools run as a fixed plan and the cards keep their standard text. The home-page example is a recorded real run, labelled with its date.
- **Subtitle data comes from the OPUS OpenSubtitles corpus,** distributed for research; only word counts derived from it are stored. A commercial version would need licensed subtitle text (from OpenSubtitles or from streaming partners).
- **Qloo describes what groups of people tend to like;** it does not predict what one person will do.
- **Privacy:** no personal data is sent to Qloo or to the language models, only the names and ids of things the learner says they like. "My list" and the level stay on the learner's device.

## Data and credits

- **Taste:** Qloo Insights API.
- **Titles:** Wikidata (CC0); original language and title casing checked on Wikipedia.
- **Subtitles:** OPUS OpenSubtitles v2024 (Lison & Tiedemann 2016), from [opensubtitles.org](https://www.opensubtitles.org/). Only word counts derived from subtitles are stored.
- **Lemmas:** spaCy, simplemma. Full references in [pipeline/README.md](pipeline/README.md).
- **Where to watch:** streaming data by JustWatch via TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB.

## Author

Brice Zemba, solo entry.

## License

MIT, see [LICENSE](LICENSE).
