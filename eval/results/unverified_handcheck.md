# Hand check of titles the automatic check could not verify (LLM-only baseline)

The automatic check (`eval/titles.py`) requires an exact Wikidata label match. 24 of the 200 titles Gemini named failed it (23 distinct titles; *Narcos: México* appears twice). Each was looked up by hand on Wikidata (Spanish and English labels) on 2026-10-22.

| Title (year as given) | Finding | Wikidata |
|---|---|---|
| Ana y los siete (2002) | Real Spanish TV series | Q3311904 |
| El marginal (2016) | Real Argentine TV series | Q23468702 |
| Flow Calle (2022) | Real film (Frank Perozo) | Q136327063 |
| OT: El Reencuentro (2016) | Real Spanish TV programme | Q27347656 |
| Ritmo Salvaje (2022) | Real Colombian TV series | Q111535897 |
| Superlópez (2018) | Real Spanish film | Q58875268 |
| Señor, dame paciencia (given as 2022) | Real Spanish film, released 2017 (year given was wrong) | Q28503418 |
| Zip y Zape y el club de la canica (2013) | Real Spanish film (English label "Zip & Zap and the Marble Gang") | Q17104642 |
| Amor con fianza (2021) | Real Spanish-language Netflix reality series (English title "Love Never Lies"); a reality show, not scripted dialogue | Q109932853 |
| Narcos: México (2018) | Real; an American production with Spanish and English dialogue | Q55657276 |
| Cantajuego | A children's music group, not a film or series | Q124540723 |
| Otro Trago | A 2019 song by Sech; no film or series found | Q65043797 |
| América Salvaje, Bronca, Crimen organizado, El Camino de Santiago, España Salvaje, Nuestra Tierra, Pacífico, Panama, Patagonia, Platino, Sucesor | No film or series with that title and year found; several are generic words. Not proven invented. | — |

## Summary

- Of the 23 distinct titles: **9 are real Spanish-language titles** (one with a wrong year), 1 is a bilingual American series, **2 are not films or series** (a music group, a song), and **11 could not be matched** to any film or series.
- So the automatic "not verified" rate (12.0%) overstates the problem; at most 11 of 200 titles (5.5%) remain unmatched after a hand check, and some of those may exist under other names.
- We do not claim these are invented. What the baseline shows reliably is level: of its 88 measured picks, 38.6% are above the learner's level.
