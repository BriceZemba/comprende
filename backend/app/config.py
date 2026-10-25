import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


def _load_dotenv() -> None:
    """Minimal .env reader so local runs need no extra dependency. Real env vars win."""
    env = REPO_ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

QLOO_API_KEY = os.environ.get("QLOO_API_KEY", "")
QLOO_BASE_URL = os.environ.get("QLOO_BASE_URL", "https://hackathon.api.qloo.com").rstrip("/")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Tried in order; the agent moves to the next model when one is slow, overloaded (503) or rate limited (429).
# Planning here is choosing Qloo tool calls, which the lite model does correctly in about a second; measured on
# 2026-10-25: flash-lite 0.5-1.5 s per call, flash 2-11 s, gemini-3.8-flash timeouts and 503s.
GEMINI_MODELS = [m.strip() for m in os.environ.get(
    "GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.5-flash").split(",") if m.strip()]
# Thinking level per model family; "minimal" keeps tool planning fast. Models not listed use their default.
GEMINI_THINKING = {"gemini-3.5-flash-lite": "minimal", "gemini-3.5-flash": "minimal"}
GEMINI_MODEL = GEMINI_MODELS[0]
CACHE_DIR = Path(os.path.expanduser(os.environ.get("COMPRENDE_CACHE", "~/.cache/comprende"))) / "qloo"
