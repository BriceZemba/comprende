"""Add Wikipedia checks to data/titles_es.json (see comprende_pipeline/wikipedia.py).

For every title:
  wp_languages  original languages from the English Wikipedia infobox, main language first
                ([] when the article has no language field, null when there is no English article)
  title_es      Spanish Wikipedia casing and punctuation when it is the same title as the Wikidata label
  label_es      the Wikidata label as fetched, kept for reference

Run after fetching titles and before build_outputs.py, which drops titles whose infobox does not list
Spanish first. Responses are cached under the pipeline cache, so reruns make no requests.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comprende_pipeline.config import DATA_DIR  # noqa: E402
from comprende_pipeline.wikipedia import (infobox_languages, infobox_wikitext, is_spanish_language,  # noqa: E402
                                          sitelinks, spanish_title)


def main():
    path = DATA_DIR / "titles_es.json"
    titles = json.loads(path.read_text(encoding="utf-8"))
    links = sitelinks([t["wikidata"] for t in titles])
    en_titles = [v["enwiki"] for v in links.values() if v and v.get("enwiki")]
    print(f"{len(en_titles)} of {len(titles)} titles have an English Wikipedia article")
    lead = infobox_wikitext(en_titles)

    catalog = {t["imdb"] for t in json.loads((DATA_DIR / "catalog_es.json").read_text(encoding="utf-8"))["titles"]}
    dropped, recased = [], 0
    for t in titles:
        link = links.get(t["wikidata"]) or {}
        t.setdefault("label_es", t.get("title_es"))
        t["wp_languages"] = infobox_languages(lead.get(link["enwiki"])) if link.get("enwiki") else None
        fixed = spanish_title(t["label_es"], link.get("eswiki"))
        if fixed != t.get("title_es"):
            recased += 1
        t["title_es"] = fixed
        if not is_spanish_language(t["wp_languages"] or []):
            dropped.append(t)
    path.write_text(json.dumps(titles, ensure_ascii=False), encoding="utf-8")

    in_cat = [t for t in dropped if t["imdb"] in catalog]
    print(f"{recased} titles re-cased; {len(dropped)} not mainly Spanish on Wikipedia, {len(in_cat)} of them measured:")
    for t in sorted(in_cat, key=lambda t: -t.get("sitelinks", 0)):
        print(f"  {t['imdb']}  {t['title_es']} ({t.get('year')})  {t['wp_languages']}")


if __name__ == "__main__":
    main()
