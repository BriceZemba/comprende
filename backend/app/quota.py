"""Remember which Gemini models have used up their daily quota, so no run waits on them again.

The free tier caps requests per model per day (20 for gemini-3.5-flash). Google answers 429 with a
"PerDay" quota id and a retry delay until the reset; calling that model again before then only adds
latency. This memory lives in the server process, which is enough: a cold start forgets it and pays one
extra failed call.
"""
import re
import time

_until: dict[str, float] = {}


def available(model: str) -> bool:
    return _until.get(model, 0.0) <= time.monotonic()


def note_error(model: str, error: BaseException) -> bool:
    """Record a daily-quota refusal; True if it was one. Per-minute limits are not recorded."""
    text = str(error)
    if not any(k in text.lower() for k in ("perday", "per day", "per-day")):  # Gemini, OpenRouter wordings
        return False
    m = re.search(r"retryDelay\W+(\d+)s", text)
    _until[model] = time.monotonic() + (int(m.group(1)) if m else 3600)
    return True
