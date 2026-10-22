"""Vercel entrypoint for the API project (root directory = repository root).

The backend lives in backend/app and reads data/ and eval/results/ from the repository,
so the API is deployed from the root and this file only exposes the FastAPI app.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("COMPRENDE_CACHE", "/tmp/comprende")  # the only writable path on Vercel

from app.main import app  # noqa: E402,F401
