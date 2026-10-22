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
# Tried in order; the agent moves to the next model when one is overloaded (503) or rate limited (429).
GEMINI_MODELS = [m.strip() for m in os.environ.get(
    "GEMINI_MODELS", "gemini-3.8-flash,gemini-3.5-flash,gemini-3.5-flash-lite").split(",") if m.strip()]
GEMINI_MODEL = GEMINI_MODELS[0]
CACHE_DIR = Path(os.path.expanduser(os.environ.get("COMPRENDE_CACHE", "~/.cache/comprende"))) / "qloo"
