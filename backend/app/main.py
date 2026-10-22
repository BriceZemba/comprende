"""HTTP API for the Comprende web app.

    uvicorn app.main:app --reload --port 8000   (from backend/)
"""
import asyncio
import json
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import config, dev_fake
from .agent import KINDS, ComprendeAgent
from .catalog import load_catalog
from .qloo import QlooClient, QlooError

app = FastAPI(title="Comprende API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

if dev_fake.ENABLED:  # development only, see app/dev_fake.py
    qloo = QlooClient(api_key="dev-fake", cache_dir=None, transport=dev_fake.transport)
else:
    qloo = QlooClient()

# Simple per-IP limit on agent runs: protects the event's Qloo quota and the model budget.
RUNS_PER_10_MIN = int(os.environ.get("RUNS_PER_10_MIN", "12"))
_runs: dict[str, deque] = defaultdict(deque)


def _allow(ip: str) -> bool:
    now, q = time.time(), _runs[ip]
    while q and now - q[0] > 600:
        q.popleft()
    if len(q) >= RUNS_PER_10_MIN:
        return False
    q.append(now)
    return True


def _client_ip(request: Request) -> str:
    """The web app proxies requests, so the visitor's address arrives in X-Forwarded-For. That header is
    trusted only when the request also carries the proxy secret; otherwise anyone could spoof it."""
    secret = os.environ.get("PROXY_SECRET", "")
    if secret and request.headers.get("x-comprende-proxy") == secret:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "?"


@app.get("/api/health")
def health():
    cat = load_catalog()
    return {
        "qloo_key": bool(config.QLOO_API_KEY),
        "fake_qloo": dev_fake.ENABLED,
        "model": config.GEMINI_MODEL if config.GEMINI_API_KEY else None,
        "measured_titles": len(cat.titles),
        "measured_titles_mapped_to_qloo": len(cat.by_qloo),
    }


@app.get("/api/method")
def method():
    """Numbers for the methods page, read from files the pipeline and evaluation scripts generate."""
    def read(path):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    return {"validation": read(config.DATA_DIR / "validation_es.json"),
            "evaluation": read(config.REPO_ROOT / "eval" / "results" / "summary.json")}


@app.get("/api/vocab/items")
def vocab_items():
    return json.loads((config.DATA_DIR / "vocab_items_es.json").read_text(encoding="utf-8"))


@app.get("/api/search")
async def search(q: str, kind: str | None = None):
    if len(q.strip()) < 2:
        return {"results": []}
    try:
        rows = await qloo.search(q.strip(), [KINDS[kind]] if kind in KINDS else None, take=8)
    except QlooError as e:
        raise HTTPException(502, detail={"code": e.code}) from e
    return {"results": [{"id": r.entity_id, "name": r.name, "kind": r.subtype.rsplit(":", 1)[-1], "year": r.year,
                         "image": r.image} for r in rows]}


class RecommendRequest(BaseModel):
    favourites_text: str = Field("", max_length=500)
    favourite_ids: dict[str, str] = Field(default_factory=dict, max_length=10)
    vocab_size: int = Field(ge=0, le=20000)
    exclude_ids: list[str] = Field(default_factory=list, max_length=50)  # titles the learner said "not for me"


@app.post("/api/recommend")
async def recommend(body: RecommendRequest, request: Request):
    if not body.favourites_text.strip() and not body.favourite_ids:
        raise HTTPException(400, detail="Tell us at least one thing you love")
    if not _allow(_client_ip(request)):
        raise HTTPException(429, detail="Too many runs from this address; try again in a few minutes")

    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event: dict):
        await queue.put(event)

    async def work():
        try:
            agent = ComprendeAgent(qloo, load_catalog(), emit)
            result = await agent.run(body.favourites_text, body.favourite_ids, body.vocab_size, body.exclude_ids)
            await queue.put({"type": "result", "result": result})
        except QlooError as e:
            await queue.put({"type": "error", "code": e.code, "text": "Qloo could not answer right now."})
        except Exception as e:  # report, do not hang the stream
            await queue.put({"type": "error", "code": type(e).__name__, "text": "Something went wrong."})
        finally:
            await queue.put(None)

    async def stream():
        task = asyncio.create_task(work())
        try:
            while (event := await queue.get()) is not None:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            task.cancel()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
