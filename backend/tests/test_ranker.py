import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.catalog import Catalog, Measured  # noqa: E402
from app.ranker import Candidate, rank  # noqa: E402

GRID_LEN = 32  # len(coverage.GRID)


def measured(imdb, flat_cov, need95=None):
    return Measured(imdb=imdb, wikidata="Q1", kind="film", title_es=f"T{imdb}", title_en=None, year=2000,
                    countries=["ESP"], coverage=[flat_cov] * GRID_LEN, vocab_for_95=need95, vocab_for_98=None)


def test_buckets_follow_coverage_thresholds_and_sort_by_taste():
    cands = [
        Candidate("a", "A", "film", affinity=0.5, measured=measured("tt1", 0.97, 2000)),
        Candidate("b", "B", "film", affinity=0.9, measured=measured("tt2", 0.96, 2500)),
        Candidate("c", "C", "film", affinity=0.8, measured=measured("tt3", 0.92, 6000)),
        Candidate("d", "D", "film", affinity=0.99, measured=measured("tt4", 0.85, 12000)),
        Candidate("e", "E", "film", affinity=0.7, measured=None),
    ]
    out = rank(cands, vocab_size=3000)
    assert [p["imdb"] for p in out["buckets"]["watch_now"]] == ["tt2", "tt1"]
    assert [p["imdb"] for p in out["buckets"]["stretch"]] == ["tt3"]
    assert out["held_back"]["imdb"] == "tt4"
    assert out["held_back"]["words_to_go"] == 9000
    assert out["buckets"]["unmeasured"][0]["name"] == "E"
    assert out["counts"] == {"watch_now": 2, "stretch": 1, "later": 1, "unmeasured": 1}
    assert out["measured_share"] == 0.8


def test_weak_taste_match_is_not_held_back():
    cands = [
        Candidate("a", "A", "film", affinity=0.9, measured=measured("tt1", 0.97, 2000)),
        Candidate("b", "B", "film", affinity=0.8, measured=measured("tt2", 0.96, 2000)),
        Candidate("d", "D", "film", affinity=0.2, measured=measured("tt4", 0.85, 12000)),
    ]
    out = rank(cands, vocab_size=3000)
    assert out["held_back"] is None
    assert out["counts"]["later"] == 1


def test_duplicates_collapse_and_words_to_go_never_negative():
    m = measured("tt9", 0.99, 1000)
    out = rank([Candidate("x", "X", "film", 0.4, measured=m), Candidate("y", "X dup", "film", 0.9, measured=m)], 5000)
    assert len(out["buckets"]["watch_now"]) == 1
    assert out["buckets"]["watch_now"][0]["words_to_go"] == 0


def test_catalog_match_by_qloo_id_or_imdb():
    a, b = measured("tt1", 0.9), measured("tt2", 0.9)
    a.qloo_id = "Q-A"
    cat = Catalog([a, b])
    assert cat.match("Q-A") is a
    assert cat.match("unknown", ["tt2"]) is b
    assert cat.match(None, ["tt404"]) is None
