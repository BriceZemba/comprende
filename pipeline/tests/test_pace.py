import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comprende_pipeline.pace import bands, level, words_per_minute  # noqa: E402


def test_words_per_minute_only_where_reliable():
    assert words_per_minute(9000, "100", "film") == 90
    assert words_per_minute(9000, 100, "series") is None   # a series' duration is ambiguous
    assert words_per_minute(9000, "25", "film") is None    # implausible running time
    assert words_per_minute(1200, "120", "film") is None   # 10 words/min: incomplete subtitle file
    assert words_per_minute(30000, "100", "film") is None  # 300 words/min: duplicated lines
    assert words_per_minute(9000, None, "film") is None
    assert words_per_minute(9000, "n/a", "film") is None


def test_levels_split_films_in_thirds():
    cuts = bands([40, 50, 60, 70, 80, 90, 100, 110, 120])
    assert len(cuts) == 2 and cuts[0] < cuts[1]
    assert level(40, cuts) == "light" and level(80, cuts) == "average" and level(120, cuts) == "dense"
    assert level(None, cuts) is None and bands([50]) == []
