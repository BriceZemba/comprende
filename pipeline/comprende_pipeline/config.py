import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
CACHE_DIR = Path(os.path.expanduser(os.environ.get("COMPRENDE_CACHE", "~/.cache/comprende")))

# OPUS OpenSubtitles v2024, Spanish, one XML file per subtitle upload.
# Lison & Tiedemann (2016), LREC. Source: https://www.opensubtitles.org/
OPUS_ES_URL = "https://object.pouta.csc.fi/OPUS-OpenSubtitles/v2024/xml/es.zip"

USER_AGENT = "comprende-pipeline/0.1 (https://github.com/BriceZemba/comprende)"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "lemmas").mkdir(parents=True, exist_ok=True)
