# Comprende

Find Spanish films and series you will love **and** can understand.

Comprende is an agent built on the [Qloo](https://www.qloo.com/) taste graph for people learning Spanish by watching native content. It starts from things you already like in any domain (shows, music, books, games), uses Qloo to find Spanish-language titles that match that taste, and ranks them by how much of the dialogue you can follow, measured from real subtitle text against your vocabulary.

> Work in progress for the Qloo Agentic Hackathon (submission period ends 2026-10-30).

## Status

- [x] Comprehension pipeline: 1,513 Spanish-original titles measured from subtitles, frequency list, vocabulary check ([pipeline/](pipeline/README.md))
- [x] Qloo client, agent and API, tested against documented Qloo response shapes ([backend/](backend/README.md))
- [x] Web app: favourites, vocabulary check, live agent steps, results
- [ ] Live Qloo run and hosted demo

## Data sources and credits

- Taste data: Qloo Insights API.
- Titles: [Wikidata](https://www.wikidata.org/) (CC0).
- Subtitles: OPUS OpenSubtitles v2024 (Lison & Tiedemann 2016), from [opensubtitles.org](https://www.opensubtitles.org/). Only word counts derived from the subtitles are stored in this repository.

## License

MIT, see [LICENSE](LICENSE).
