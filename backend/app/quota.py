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
    m = re.search(r"retryDelay\W+(\d+)s", text)  # Gemini: seconds until reset
    reset = re.search(r"X-RateLimit-Reset\W+(\d{12,})", text)  # OpenRouter: reset time, epoch milliseconds
    wait = int(m.group(1)) if m else (int(reset.group(1)) / 1000 - time.time() if reset else 3600)
    _until[model] = time.monotonic() + max(60.0, wait)
    return True
