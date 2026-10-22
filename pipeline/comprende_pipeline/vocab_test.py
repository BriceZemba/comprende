"""Yes/No vocabulary-size check.

The learner sees real Spanish words sampled from frequency bands and made-up
pseudowords, and says which ones they know. Pseudowords catch over-claiming
(Meara & Buxton 1987). Per band, the hit rate is corrected for guessing with the
false-alarm rate, then scaled by the band's width to estimate vocabulary size.
"""
import math
import random
from collections import Counter, defaultdict

BANDS = [(1, 1000), (1001, 2000), (2001, 3000), (3001, 5000), (5001, 8000), (8001, 12000)]
WORDS_PER_BAND = 8
PSEUDOWORDS = 16
CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}

# Kept out of the item pool so the check is safe to show anyone.
BLOCKLIST = {
    "puta", "puto", "mierda", "joder", "coño", "cabrón", "cabron", "pendejo", "culo", "verga", "polla",
    "chingar", "chingada", "maricón", "marica", "follar", "carajo", "hostia", "gilipollas", "pinche",
    "mamar", "mamón", "zorra", "cojón", "cojones", "concha", "imbécil", "estúpido", "idiota", "culero",
    "cagar", "joto", "perra", "puñeta", "teta", "pene", "violar", "ojete", "chupar", "pedo", "cachondo",
    "nazi", "negro", "gordo", "retrasado", "subnormal", "drogar", "droga", "suicidar", "suicidio",
    "pelotudez", "pelotudo", "boludo", "boludez", "huevón", "weón", "carajo",
}

# Removed after reading the generated list: an interjection ("chist"), and pseudowords that look
# English or too close to a real form (a learner could rightly think they know them).
REVIEWED_OUT = {"clang", "querillo", "camete", "chist"}


def build_items(freq_rows, main_pos: dict[str, str], known_forms: set[str], seed: int = 7,
                is_dictionary_word=None) -> dict:
    """Pick real words per band and generate pseudowords. freq_rows = [(lemma, cd, count)] by rank.

    is_dictionary_word(word) -> bool, when given, must accept every real item (a dictionary base form)
    and reject every pseudoword (no real Spanish word or inflected form)."""
    is_word = is_dictionary_word or (lambda w: False)
    rng = random.Random(seed)
    real = []
    for lo, hi in BANDS:
        pool = [
            lemma for lemma, _, _ in freq_rows[lo - 1 : hi]
            if main_pos.get(lemma) in CONTENT_POS
            and 4 <= len(lemma) <= 12
            and lemma.isalpha()
            and lemma in known_forms  # the lemma itself is attested as a word, not a lemmatiser artefact
            and lemma not in BLOCKLIST
            and lemma not in REVIEWED_OUT
            and (is_dictionary_word is None or is_word(lemma))
        ]
        for lemma in rng.sample(pool, WORDS_PER_BAND):
            real.append({"word": lemma, "real": True, "band": [lo, hi]})
    lexicon = {r[0] for r in freq_rows} | known_forms
    training = [r[0] for r in freq_rows[:8000] if r[0].isalpha() and len(r[0]) >= 4]
    fakes = pseudowords(training, lexicon, PSEUDOWORDS, rng, reject=is_word)
    items = real + [{"word": w, "real": False} for w in fakes]
    return {
        "language": "es",
        "bands": BANDS,
        "items": items,
        "method": "Yes/No test (Meara & Buxton 1987); per-band hit rate corrected for guessing.",
    }


def pseudowords(training: list[str], lexicon: set[str], n: int, rng: random.Random, reject=None) -> list[str]:
    """Generate word-like strings from a character trigram model, rejecting any attested word."""
    trans: dict[str, Counter] = defaultdict(Counter)
    for w in training:
        s = "^^" + w + "$"
        for i in range(len(s) - 2):
            trans[s[i : i + 2]][s[i + 2]] += 1
    out: list[str] = []
    while len(out) < n:
        ctx, w = "^^", ""
        while True:
            options = trans[ctx]
            ch = rng.choices(list(options), weights=list(options.values()))[0]
            if ch == "$":
                break
            w += ch
            ctx = ctx[1] + ch
            if len(w) > 11:
                break
        if (5 <= len(w) <= 10 and w not in lexicon and w not in out and not _near_lexicon(w, lexicon)
                and not (reject and reject(w)) and w not in REVIEWED_OUT):
            out.append(w)
    return out


def _near_lexicon(w: str, lexicon: set[str]) -> bool:
    """Reject strings one plural or accent away from a real word, which learners would rightly accept."""
    plain = w.translate(str.maketrans("áéíóú", "aeiou"))
    variants = {plain, w.rstrip("s"), w + "s", w.rstrip("es")}
    return any(v in lexicon for v in variants)


def _round(x: float, digits: int = 0) -> float:
    """Round half up, like JavaScript's Math.round, so the web app gives identical numbers."""
    scale = 10**digits
    return math.floor(x * scale + 0.5) / scale


def estimate_vocab(items: list[dict], answers: dict[str, bool], bands=BANDS) -> dict:
    """Estimate known lemmas from yes/no answers. Missing answers count as 'no'."""
    fakes = [i for i in items if not i["real"]]
    false_alarm = sum(answers.get(i["word"], False) for i in fakes) / len(fakes) if fakes else 0.0
    total, per_band = 0.0, []
    for lo, hi in bands:
        band_items = [i for i in items if i["real"] and i["band"] == [lo, hi]]
        hits = sum(answers.get(i["word"], False) for i in band_items) / len(band_items)
        corrected = 0.0 if false_alarm >= 1 else max(0.0, (hits - false_alarm) / (1 - false_alarm))
        per_band.append({"band": [lo, hi], "hit_rate": _round(hits, 3), "corrected": _round(corrected, 3)})
        total += corrected * (hi - lo + 1)
    return {
        "vocab_size": int(_round(total)),
        "false_alarm_rate": _round(false_alarm, 3),
        "reliable": false_alarm <= 0.25,
        "bands": per_band,
    }
