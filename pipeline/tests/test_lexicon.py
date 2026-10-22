import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("simplemma")
from comprende_pipeline.lexicon import normalize_counts, normalize_lemma  # noqa: E402

CASES = {
    # inflected forms the tagger left as lemmas
    "quieras": "querer", "moleste": "molestar", "esperen": "esperar", "avisé": "avisar",
    # attached pronouns
    "déjalo": "dejar", "acompañarte": "acompañar", "confesarme": "confesar", "mírame": "mirar",
    "cómetelo": "comer", "escríbeme": "escribir", "dárselo": "dar", "decirle": "decir",
    # irregular imperatives with pronouns
    "dímelo": "decir", "hazlo": "hacer", "dame": "dar", "dile": "decir", "vete": "ir", "ponte": "poner",
    # pronominal verbs count as the base verb
    "cállate": "callar", "vámonos": "ir",
    # ordinary words must not change
    "casa": "casa", "ciudad": "ciudad", "dios": "dios", "clase": "clase", "nadie": "nadie", "hola": "hola",
    # unknown words keep the tagger's lemma rather than a dictionary guess
    "jueguecito": "jueguecito",
}


@pytest.mark.parametrize("word,expected", CASES.items())
def test_normalize_lemma(word, expected):
    assert normalize_lemma(word) == expected


def test_normalize_counts_merges():
    assert normalize_counts({"dejar": 3, "déjalo": 2, "casa": 1}) == {"dejar": 5, "casa": 1}
