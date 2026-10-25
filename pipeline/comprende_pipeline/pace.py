"""Dialogue density: subtitle words per minute of a film's running time.

Coverage says which words a learner knows, not how fast they come. Subtitles carry no reliable speech
timing here (only word counts are kept), but the OpenSubtitles metadata gives the film's running time,
so words per minute of runtime measures how much talking there is. It is not speech rate: silent
scenes count in the minutes, and subtitles condense speech. It is shown only where it can be trusted:
- films only (a series' "duration" may be one episode or the whole season);
- a plausible running time (40-240 min);
- a plausible density (30-180 words/min): below, the subtitle file is likely incomplete; above, likely
  duplicated lines.
"""
import statistics

MIN_RUNTIME, MAX_RUNTIME = 40, 240
MIN_WPM, MAX_WPM = 30, 180


def words_per_minute(tokens: int, duration_min, kind: str) -> int | None:
    """Rounded words per minute of runtime, or None when it cannot be trusted."""
    try:
        minutes = float(duration_min)
    except (TypeError, ValueError):
        return None
    if kind != "film" or not MIN_RUNTIME <= minutes <= MAX_RUNTIME or tokens <= 0:
        return None
    wpm = tokens / minutes
    return round(wpm) if MIN_WPM <= wpm <= MAX_WPM else None


def bands(values: list[int]) -> list[float]:
    """Cut points between little, average and lots of dialogue: the thirds of the measured films."""
    if len(values) < 3:
        return []
    q = statistics.quantiles(values, n=3)
    return [round(q[0], 1), round(q[1], 1)]


def level(wpm: int | None, cuts: list[float]) -> str | None:
    if wpm is None or len(cuts) != 2:
        return None
    return "light" if wpm < cuts[0] else "dense" if wpm >= cuts[1] else "average"
