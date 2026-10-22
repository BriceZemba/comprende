import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comprende_pipeline.coverage import GRID, coverage_at, coverage_curve, frequency_ranks, vocab_needed  # noqa: E402


def test_frequency_ranks_prefers_contextual_diversity():
    lexicons = [
        {"lemmas": {"casa": 1, "dragón": 50}},
        {"lemmas": {"casa": 1}},
        {"lemmas": {"casa": 1, "dragón": 1}},
        {"lemmas": {"dragón": 1}},
    ]
    rows = frequency_ranks(lexicons, min_titles=1)
    # dragón appears in 3 titles with 52 tokens; casa in 3 titles with 3 tokens: tie on CD, count breaks it.
    assert [r[0] for r in rows] == ["dragón", "casa"]
    rows = frequency_ranks(lexicons + [{"lemmas": {"casa": 1}}], min_titles=1)
    assert rows[0][0] == "casa"


def test_frequency_ranks_drops_rare_lemmas():
    rows = frequency_ranks([{"lemmas": {"a": 1, "b": 1}}, {"lemmas": {"a": 1}}], min_titles=2)
    assert [r[0] for r in rows] == ["a"]


def test_coverage_curve_counts_marginal_words_as_known():
    rank = {"ser": 1, "casa": 300, "dragón": 5000}
    curve = coverage_curve({"ser": 6, "casa": 2, "dragón": 1, "inexistente": 1}, marginal=10, tokens=20, rank=rank)
    assert len(curve) == len(GRID)
    assert curve[GRID.index(250)] == 0.8  # 10 marginal + 6 "ser"
    assert curve[GRID.index(500)] == 0.9  # + 2 "casa"
    assert curve[GRID.index(5000)] == 0.95  # + 1 "dragón"; the unranked lemma stays unknown
    assert curve[-1] == 0.95


def test_coverage_curve_is_monotonic_and_handles_empty():
    curve = coverage_curve({"a": 3, "b": 2}, 0, 5, {"a": 900, "b": 15000})
    assert curve == sorted(curve)
    assert coverage_curve({}, 0, 0, {}) == [0.0] * len(GRID)


def test_coverage_at_interpolates_between_grid_points():
    curve = [0.0] * len(GRID)
    i = GRID.index(1000)
    curve[i], curve[i + 1] = 0.90, 0.94  # 1000 -> 1500
    for k in range(i + 2, len(GRID)):
        curve[k] = 0.94
    assert abs(coverage_at(curve, 1250) - 0.92) < 1e-9
    assert coverage_at(curve, 50000) == 0.94
    assert coverage_at(curve, 0) == 0.0


def test_vocab_needed():
    curve = [min(1.0, 0.8 + 0.01 * k) for k in range(len(GRID))]
    assert vocab_needed(curve, 0.8) == GRID[0]
    assert vocab_needed(curve, 0.95) == GRID[15]
    assert vocab_needed([0.5] * len(GRID), 0.95) is None
