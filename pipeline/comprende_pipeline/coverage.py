"""Frequency ranks and lexical coverage.

Coverage is the share of running words in a title that a learner knows. Research on
reading and listening puts adequate comprehension at roughly 95% coverage and
comfortable, unassisted comprehension at about 98% (Laufer 1989; Hu & Nation 2000;
Nation 2006). For films, Webb & Rodgers (2009) estimated that 3,000 word families
plus proper nouns and marginal words reach 95% coverage.

A learner who knows the V most frequent lemmas is modelled as knowing exactly
those lemmas. This is the standard simplification behind vocabulary-size tests.
"""
from bisect import bisect_right
from collections import Counter
from typing import Iterable

# Vocabulary sizes at which each title's coverage is stored (in lemmas).
GRID = list(range(250, 1000, 250)) + list(range(1000, 10000, 500)) + list(range(10000, 20001, 1000))


def frequency_ranks(lexicons: Iterable[dict], min_titles: int = 3) -> list[tuple[str, int, int]]:
    """Rank lemmas by contextual diversity (number of titles they appear in), then by count.

    Contextual diversity predicts word knowledge better than raw frequency
    (Adelman, Brown & Quesada 2006) and is the measure behind SUBTLEX-ESP
    (Cuetos et al. 2011). It also stops one film's character catchphrase from
    looking like a common word.
    """
    cd, count = Counter(), Counter()
    for lex in lexicons:
        for lemma, c in lex["lemmas"].items():
            cd[lemma] += 1
            count[lemma] += c
    rows = [(lemma, cd[lemma], count[lemma]) for lemma in cd if cd[lemma] >= min_titles]
    rows.sort(key=lambda r: (-r[1], -r[2], r[0]))
    return rows


def coverage_curve(lemmas: dict[str, int], marginal: int, tokens: int, rank: dict[str, int]) -> list[float]:
    """Coverage at each vocabulary size in GRID. Lemmas outside the ranked list count as unknown."""
    if tokens == 0:
        return [0.0] * len(GRID)
    by_rank = sorted((rank.get(lemma, 10**9), c) for lemma, c in lemmas.items())
    curve, known, i = [], marginal, 0
    for v in GRID:
        while i < len(by_rank) and by_rank[i][0] <= v:
            known += by_rank[i][1]
            i += 1
        curve.append(round(known / tokens, 4))
    return curve


def coverage_at(curve: list[float], vocab_size: float) -> float:
    """Linear interpolation of a stored curve at any vocabulary size."""
    if vocab_size <= GRID[0]:
        return curve[0] * vocab_size / GRID[0] if vocab_size > 0 else 0.0
    if vocab_size >= GRID[-1]:
        return curve[-1]
    j = bisect_right(GRID, vocab_size)
    x0, x1, y0, y1 = GRID[j - 1], GRID[j], curve[j - 1], curve[j]
    return y0 + (y1 - y0) * (vocab_size - x0) / (x1 - x0)


def fit_for(coverage: float) -> str:
    """Label used in the app: 98% comfortable, 95% watchable (Hu & Nation 2000; Nation 2006)."""
    if coverage >= 0.98:
        return "comfortable"
    if coverage >= 0.95:
        return "watchable"
    if coverage >= 0.90:
        return "stretch"
    return "later"


def vocab_needed(curve: list[float], target: float) -> int | None:
    """Smallest grid vocabulary size that reaches the target coverage, or None if never reached."""
    for v, c in zip(GRID, curve):
        if c >= target:
            return v
    return None
