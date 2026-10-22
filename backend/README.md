# Comprende backend

FastAPI service that runs the agent: Qloo for taste, the subtitle pipeline for comprehension, Gemini for planning and wording.

## How a run works

1. **Resolve favourites.** Each thing the learner loves (a show, an artist, a book, a game) is looked up with Qloo `/search`.
2. **Recommend Spanish titles.** Qloo `/v2/insights` with the favourites as `signal.interests.entities`, `filter.type` = movie or TV show, and `filter.release_country` set to Spanish-speaking countries. `feature.explainability` returns which favourite drove each pick.
3. **Score measured titles.** The same taste signal is applied to the titles whose dialogue we measured, through `filter.results.entities`, so well-understood titles are not missed just because they rank below the top 40.
4. **Rank.** `app/ranker.py` groups titles by how much of the dialogue the learner can follow (≥ 95% watch now, 90–95% stretch, < 90% later) and orders each group by Qloo affinity. It also picks the title the learner would most love but cannot follow yet.
5. **Explain.** Gemini writes the short "why" for each pick from the tool results. It never produces a number: affinity comes from Qloo and coverage from subtitles.

If Gemini is unavailable the same tools run in a fixed order (`ComprendeAgent._run_fixed`), so the app still answers.

## Run locally

```bash
pip install -r requirements.txt
cp ../.env.example ../.env   # add QLOO_API_KEY and GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```

Endpoints: `GET /api/health`, `GET /api/vocab/items`, `GET /api/search?q=`, `POST /api/recommend` (server-sent events: `step`, `warning`, `message`, then `result`).

## Scripts

- `scripts/qloo_spike.py`: live checks of the key, id mapping, Spanish-language filtering and explainability; saves responses to `tests/fixtures/live/`.
- `scripts/build_qloo_map.py`: maps every measured title to its Qloo entity by IMDb id, then Wikidata id (`data/qloo_map_es.json`).

## Tests

```bash
python -m pytest -q tests
```

Qloo is mocked with response shapes from the Qloo documentation; no key is needed.

## Quota and safety

- The Qloo key stays on the server. Responses are cached on disk for 7 days.
- Agent runs are limited per IP (`RUNS_PER_10_MIN`, default 12).
- No personal data is sent to Qloo: only the entity ids of things the learner says they like.
