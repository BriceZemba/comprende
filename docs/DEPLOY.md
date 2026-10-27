# Deploying Comprende

Two Vercel projects from this repository.

| Project | Root directory | What it serves |
|---|---|---|
| `comprende-api` | `.` (repository root) | FastAPI app via `api/index.py`; reads `data/` and `eval/results/` |
| `comprende` | `web` | Next.js app; proxies `/api/*` to the API project |

## Environment variables

API project:

| Name | Value |
|---|---|
| `QLOO_API_KEY` | hackathon key (server only) |
| `QLOO_BASE_URL` | `https://hackathon.api.qloo.com` |
| `GEMINI_API_KEY` | Gemini key |
| `PROXY_SECRET` | long random string, same as the web project |
| `RUNS_PER_10_MIN` | optional, default 12 |

Web project:

| Name | Value |
|---|---|
| `BACKEND_URL` | the API project's production URL, e.g. `https://comprende-api.vercel.app` |
| `PROXY_SECRET` | same value as the API project |

`COMPRENDE_DEV_FAKE_QLOO` must never be set in a deployment.

## Checks after each deploy

1. `GET <api>/api/health` returns `qloo_key: true`, `fake_qloo: false`, and a non-zero `measured_titles_mapped_to_qloo`.
2. The home page shows no "Development mode" banner.
3. A run streams its steps one by one (not all at once at the end).
