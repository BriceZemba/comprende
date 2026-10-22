import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comprende_pipeline.vocab_test import BANDS, build_items, estimate_vocab, pseudowords  # noqa: E402


def _items():
    items = []
    for lo, hi in BANDS:
        items += [{"word": f"w{lo}_{k}", "real": True, "band": [lo, hi]} for k in range(8)]
    items += [{"word": f"fake{k}", "real": False} for k in range(16)]
    return items


def test_knows_everything_no_false_alarms():
    items = _items()
    answers = {i["word"]: i["real"] for i in items}
    est = estimate_vocab(items, answers)
    assert est["vocab_size"] == 12000
    assert est["reliable"]


def test_knows_first_two_bands_only():
    items = _items()
    answers = {i["word"]: i["real"] and i["band"][1] <= 2000 for i in items}
    assert estimate_vocab(items, answers)["vocab_size"] == 2000


def test_saying_yes_to_everything_scores_zero_and_unreliable():
    items = _items()
    est = estimate_vocab(items, {i["word"]: True for i in items})
    assert est["vocab_size"] == 0
    assert not est["reliable"]


def test_false_alarms_discount_hits():
    items = _items()
    fakes = [i["word"] for i in items if not i["real"]]
    answers = {i["word"]: i["real"] and i["band"][1] <= 1000 for i in items}
    answers.update({w: True for w in fakes[:4]})  # 25% false alarms
    est = estimate_vocab(items, answers)
    # band 1: (1 - .25) / (1 - .25) = 1 -> 1000; other bands: max(0, (0 - .25)/.75) = 0
    assert est["vocab_size"] == 1000
    assert est["false_alarm_rate"] == 0.25


def test_pseudowords_never_real_and_deterministic():
    training = ["casa", "camino", "cantar", "mesa", "perro", "comida", "trabajo", "momento", "persona", "verdad"] * 3
    lexicon = set(training)
    a = pseudowords(training, lexicon, 5, random.Random(1))
    b = pseudowords(training, lexicon, 5, random.Random(1))
    assert a == b
    assert all(w not in lexicon and 5 <= len(w) <= 10 for w in a)


def _alpha(k: int) -> str:
    s = ""
    for _ in range(4):
        s += "abcdefghijklmnoprstu"[k % 20]
        k //= 20
    return "ca" + s + "o"


def test_build_items_shape():
    rows = [(_alpha(k), 10, 10) for k in range(12000)]
    pos = {r[0]: "NOUN" for r in rows}
    forms = {r[0] for r in rows}
    out = build_items(rows, pos, forms, seed=3)
    real = [i for i in out["items"] if i["real"]]
    fake = [i["word"] for i in out["items"] if not i["real"]]
    assert len(real) == 48 and len(fake) == 16
    assert not set(fake) & forms
    for i in real:
        rank = next(k for k, r in enumerate(rows, 1) if r[0] == i["word"])
        assert i["band"][0] <= rank <= i["band"][1]
