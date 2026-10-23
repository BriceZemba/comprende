import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comprende_pipeline.wikipedia import infobox_languages, is_spanish_language, spanish_title  # noqa: E402

EXTINCTION = """{{Infobox film
| name = Extinction
| country = {{plainlist|
* Spain
* Hungary
}}
| language = English
| budget = $6 million
}}
'''Extinction''' is a 2015 film."""

WHITE_LINES = """{{Infobox television
| language = {{ubl|[[English language|English]]|[[Spanish language|Spanish]]}}<!-- main first -->
| num_seasons = 1
}}"""

LIBERATOR = """{{Infobox film
| language       = Spanish<br>English<br>French
| budget         = $50 million
}}"""

NO_FIELD = """{{Infobox film
| name = Roma
| country = Mexico
}}"""


def test_infobox_languages_in_listed_order():
    assert infobox_languages(EXTINCTION) == ["en"]
    assert infobox_languages(WHITE_LINES) == ["en", "es"]
    assert infobox_languages(LIBERATOR) == ["es", "en", "fr"]
    assert infobox_languages(NO_FIELD) == []
    assert infobox_languages(None) == []


def test_spanish_must_be_listed_and_english_not_first():
    assert not is_spanish_language(["en"])
    assert not is_spanish_language(["en", "es"])
    assert not is_spanish_language(["ca"])  # Catalan only: Spanish subtitles are a translation
    assert is_spanish_language(["es", "en", "fr"])
    assert is_spanish_language(["ca", "es"])  # bilingual, either order
    assert is_spanish_language([])  # no evidence either way: keep


def test_spanish_title_uses_wikipedia_casing_only_for_the_same_title():
    assert spanish_title("Que dios nos perdone", "Que Dios nos perdone") == "Que Dios nos perdone"
    assert spanish_title("El Desorden Que Dejas", "El desorden que dejas (serie de televisión)") == "El desorden que dejas"
    assert spanish_title("Bienvenido, Mister Marshall", "¡Bienvenido, Mister Marshall!") == "¡Bienvenido, Mister Marshall!"
    assert spanish_title("Libertador,", "Libertador (película)") == "Libertador"
    # A different article title is not used, but stray punctuation is still removed.
    assert spanish_title("Roma", "Roma (película de 2018)") == "Roma"
    assert spanish_title("Libertador,", None) == "Libertador"
    assert spanish_title("Celda 211", "Celda 211 (película)") == "Celda 211"
    assert spanish_title("Los amantes", "Los amantes pasajeros") == "Los amantes"
    # Official Title Case in the article is not copied over a sentence-case label.
    assert spanish_title("La reina del flow", "La Reina del Flow") == "La reina del flow"
