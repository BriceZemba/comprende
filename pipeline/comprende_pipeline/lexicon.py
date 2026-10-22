"""Lemmatise subtitle tokens and sort them into the counts coverage needs.

Following the lexical-coverage method used for film and TV (Webb & Rodgers 2009),
proper nouns and interjections count as known: a learner does not need to have
learned "Madrid" or "eh" to follow a scene. Punctuation and numbers are ignored.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache

MARGINAL_POS = {"PROPN", "INTJ"}
SKIP_POS = {"PUNCT", "SYM", "NUM", "SPACE", "X"}
WORD_RE = re.compile(r"^[a-záéíóúüñ]+(?:-[a-záéíóúüñ]+)*$")


@dataclass
class TitleLexicon:
    lemmas: Counter = field(default_factory=Counter)  # content lemma -> token count
    pos: Counter = field(default_factory=Counter)  # (lemma, pos) -> count, to pick a lemma's main POS
    forms: set = field(default_factory=set)  # surface forms seen, used to keep pseudowords unreal
    marginal: int = 0  # proper nouns and interjections
    tokens: int = 0  # all word tokens (content + marginal)

    def to_json(self) -> dict:
        return {
            "lemmas": dict(self.lemmas),
            "pos": {f"{l}|{p}": c for (l, p), c in self.pos.items()},
            "forms": sorted(self.forms),
            "marginal": self.marginal,
            "tokens": self.tokens,
        }

    @classmethod
    def from_json(cls, d: dict) -> "TitleLexicon":
        pos = Counter({tuple(k.rsplit("|", 1)): v for k, v in d["pos"].items()})
        return cls(Counter(d["lemmas"]), pos, set(d["forms"]), d["marginal"], d["tokens"])


# Pronouns that Spanish attaches to infinitives, gerunds and imperatives ("déjalo", "dímelo",
# "acompañarte"). Longest first so "selo" is tried before "lo".
CLITICS = sorted({"me", "te", "se", "lo", "la", "le", "los", "las", "les", "nos", "os",
                  "melo", "mela", "telo", "tela", "selo", "sela", "selos", "selas", "noslo", "nosla"},
                 key=len, reverse=True)
_DEACCENT = str.maketrans("áéíóú", "aeiou")
# Irregular tú imperatives that take clitics ("hazlo", "dame", "dile", "vete", "ponte").
IRREGULAR_IMPERATIVES = {"haz": "hacer", "da": "dar", "di": "decir", "ve": "ir", "pon": "poner",
                         "ten": "tener", "ven": "venir", "sal": "salir", "se": "ser"}


def _dictionary_lemma(word: str) -> str | None:
    """Lemma from a dictionary-backed lemmatiser, only when the word form is in its dictionary
    (simplemma guesses wrongly on unknown forms, e.g. "jueguecito" -> "jueguecitar")."""
    import simplemma

    if not simplemma.is_known(word, lang="es"):
        return None
    lemma = simplemma.lemmatize(word, lang="es")
    # Pronominal infinitives ("callarse", "irse") are the same word for a learner as "callar", "ir".
    if lemma.endswith(("arse", "erse", "irse")) and len(lemma) >= 4:
        lemma = lemma[:-2]
    # The dictionary occasionally maps a form to a non-word ("dímelo" -> "dimir"): reject those.
    return lemma if simplemma.is_known(lemma, lang="es") else None


def _verb_lemma(stem: str) -> str | None:
    """A stem left after removing a clitic is a verb form: prefer an infinitive reading
    ("mira" from "mírame" is the imperative of "mirar", not the noun "mira")."""
    import simplemma

    for cand in (stem + "r", stem[:-1] + "ar", stem[:-1] + "er", stem[:-1] + "ir"):
        if cand.endswith(("ar", "er", "ir")) and simplemma.is_known(cand, lang="es") \
                and simplemma.lemmatize(cand, lang="es") == cand:
            return cand
    found = _dictionary_lemma(stem)
    return found if found and found.endswith(("ar", "er", "ir")) else None


@lru_cache(maxsize=None)
def normalize_lemma(lemma: str) -> str:
    """Repair spaCy lemmas that are still inflected or carry attached pronouns.

    Order: irregular imperative + clitic ("dímelo"); dictionary lookup of the form itself; then
    strip one or two clitic pronouns, remove the stress accent the clitic forced, and look the
    stem up; else keep spaCy's lemma.
    """
    known = _dictionary_lemma(lemma)
    is_other_word = known is not None and not known.endswith(("ar", "er", "ir"))  # "dios" is not "di" + "os"
    for c in CLITICS if not is_other_word else []:
        if lemma.endswith(c):
            rest = lemma[: -len(c)]
            for c2 in [""] + CLITICS:  # up to two pronouns: "dí-me-lo"
                if rest.endswith(c2):
                    stem = rest[: len(rest) - len(c2)].translate(_DEACCENT)
                    if stem in IRREGULAR_IMPERATIVES:
                        return IRREGULAR_IMPERATIVES[stem]
    found = known
    if found:
        return found
    stem = lemma
    for _ in range(2):
        for c in CLITICS:
            if stem.endswith(c) and len(stem) - len(c) >= 3:
                stem = stem[: -len(c)]
                break
        else:
            break
        plain = stem.translate(_DEACCENT)
        found = _dictionary_lemma(stem) if stem != plain else None
        found = found if found and found.endswith(("ar", "er", "ir")) else None
        found = found or _verb_lemma(plain)
        if found:
            return found
    return lemma


def normalize_counts(lemmas: dict[str, int]) -> Counter:
    out: Counter = Counter()
    for lemma, c in lemmas.items():
        out[normalize_lemma(lemma)] += c
    return out


def load_nlp():
    import spacy

    return spacy.load("es_core_news_sm", disable=["parser", "ner"])


def lexicon_from_sentences(nlp, sentences: list[list[str]], batch_size: int = 256) -> TitleLexicon:
    from spacy.tokens import Doc

    lex = TitleLexicon()
    docs = (Doc(nlp.vocab, words=words) for words in sentences)
    for doc in nlp.pipe(docs, batch_size=batch_size):
        for tok in doc:
            if tok.pos_ in SKIP_POS:
                continue
            text = tok.text.lower()
            if tok.pos_ in MARGINAL_POS:
                lex.marginal += 1
                lex.tokens += 1
                continue
            lemma = tok.lemma_.lower()
            if not WORD_RE.match(lemma):
                continue
            lex.tokens += 1
            lex.lemmas[lemma] += 1
            lex.pos[(lemma, tok.pos_)] += 1
            if WORD_RE.match(text):
                lex.forms.add(text)
    return lex
