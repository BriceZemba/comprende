"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

interface Validation {
  titles: number;
  median_vocab_for_95: number;
  p25_vocab_for_95: number;
  p75_vocab_for_95: number;
  median_vocab_for_98: number;
  median_coverage_at_1000: number;
  median_coverage_at_3000: number;
  genre_check?: { hypothesis: string; result: string; animation_family: number; drama: number; animation_family_titles: number };
}

interface SystemSummary {
  label: string;
  run_at: string | null;
  titles: number;
  spanish_original: number;
  not_spanish: number;
  unverified: number;
  distinct_share: number;
  mean_jaccard: number;
  fit_n: number;
  fit_95: number | null;
  fit_below_90: number | null;
  first5_n: number;
  first5_95: number | null;
  first5_below_90: number | null;
  repeated: [string, number][];
}

// One decimal, same as eval/results/report.md and data/validation_es.md.
const pct = (x: number | null | undefined) => (x == null ? "n/a" : `${(x * 100).toFixed(1)}%`);
const n = (x: number) => x.toLocaleString();

export default function Method() {
  const [data, setData] = useState<{ validation: Validation | null; evaluation: Record<string, SystemSummary> | null } | null>(null);
  useEffect(() => { fetch("/api/method").then((r) => r.json()).then(setData).catch(() => setData({ validation: null, evaluation: null })); }, []);
  const v = data?.validation;
  const systems = data?.evaluation ? Object.values(data.evaluation) : [];

  return (
    <main className="mx-auto max-w-3xl px-4 pb-24 sm:px-8">
      <header className="flex items-center justify-between py-6">
        <Link href="/" className="font-display text-2xl">comprende</Link>
        <Link href="/" className="text-sm text-muted hover:text-ink">Try it</Link>
      </header>
      <h1 className="font-display text-4xl sm:text-5xl">How Comprende works, and how we checked it</h1>

      <section className="mt-10 space-y-4 leading-relaxed">
        <h2 className="font-display text-2xl">Taste: the Qloo taste graph</h2>
        <p>
          Your favourites, from any domain, are looked up in Qloo and passed as signals to Qloo&apos;s Insights API.
          Qloo returns films and series originally released in Spanish-speaking countries that audiences with similar
          tastes enjoy, scores the titles we measured against the same signals, and reports which favourite drove each
          match. Qloo describes what groups of people tend to like; it does not predict what one person will do.
        </p>
      </section>

      <section className="mt-10 space-y-4 leading-relaxed">
        <h2 className="font-display text-2xl">Difficulty: words you know, in real dialogue</h2>
        <p>
          For each Spanish-original film or series with subtitles in the open OPUS OpenSubtitles corpus, we count the
          words in its dialogue and rank Spanish words by how many titles use them. If you know the {n(3000)} most common
          words, the share of a title&apos;s running words you know is its <em>coverage</em> for you. Proper names and
          interjections count as known.
        </p>
        <p>
          Studies of reading and listening put adequate comprehension at about 95% coverage and comfortable,
          unassisted comprehension near 98% (Hu &amp; Nation 2000; Nation 2006). Comprende uses 95% for
          &ldquo;watch now&rdquo; and 90–95% for &ldquo;a good stretch&rdquo;.
        </p>
        <p>
          Your vocabulary comes from a yes/no word check: 48 real words from six frequency bands and 16 made-up words.
          Saying yes to made-up words lowers the estimate, the standard correction for guessing (Meara &amp; Buxton 1987).
        </p>
      </section>

      <section className="mt-10 space-y-4">
        <h2 className="font-display text-2xl">Does the difficulty measure behave as research predicts?</h2>
        {v ? (
          <ul className="list-disc space-y-2 pl-5 leading-relaxed">
            <li>
              Across {n(v.titles)} measured titles, the median title needs <strong>{n(v.median_vocab_for_95)} words</strong> for
              95% coverage (middle half: {n(v.p25_vocab_for_95)}–{n(v.p75_vocab_for_95)}) and {n(v.median_vocab_for_98)} for 98%.
              Webb &amp; Rodgers (2009) found about 3,000 word families plus proper nouns give 95% coverage of English film
              dialogue.
            </li>
            <li>Knowing 1,000 words covers {pct(v.median_coverage_at_1000)} of the median title; 3,000 words cover {pct(v.median_coverage_at_3000)}.</li>
            {v.genre_check && (
              <li>
                A check that did <strong>not</strong> work out: we expected animation and family titles to be easier
                than dramas. They are not ({pct(v.genre_check.animation_family)} vs {pct(v.genre_check.drama)} coverage
                at 3,000 words, on only {v.genre_check.animation_family_titles} animated or family titles).
              </li>
            )}
          </ul>
        ) : <p className="text-muted">Loading…</p>}
      </section>

      <section className="mt-10 space-y-4">
        <h2 className="font-display text-2xl">Compared with asking a language model</h2>
        <p className="leading-relaxed">
          The same 20 fixed taste profiles (three favourites and a vocabulary size each) went to three systems: a
          language model on its own; Comprende without Qloo, ranking by general popularity instead of taste; and
          Comprende. Every title was checked against Wikidata and against our measured dialogue.
        </p>
        {systems.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead><tr className="border-b border-line"><th className="py-2 pr-4">Measure</th>{systems.map((s) => <th key={s.label} className="py-2 pr-4">{s.label}</th>)}</tr></thead>
              <tbody>
                {([
                  ["Verified as originally Spanish", (s: SystemSummary) => pct(s.spanish_original)],
                  ["Real title, not originally Spanish", (s: SystemSummary) => pct(s.not_spanish)],
                  ["Not verified automatically", (s: SystemSummary) => pct(s.unverified)],
                  ["Different titles across profiles", (s: SystemSummary) => pct(s.distinct_share)],
                  ["Titles with measured dialogue", (s: SystemSummary) => String(s.fit_n)],
                  ["…followable at the learner's level (≥ 95%)", (s: SystemSummary) => pct(s.fit_95)],
                  ["…too hard (< 90%)", (s: SystemSummary) => pct(s.fit_below_90)],
                  ["First five picks with measured dialogue", (s: SystemSummary) => String(s.first5_n)],
                  ["…followable (≥ 95%)", (s: SystemSummary) => pct(s.first5_95)],
                  ["…too hard (< 90%)", (s: SystemSummary) => pct(s.first5_below_90)],
                ] as [string, (s: SystemSummary) => string][]).map(([label, f]) => (
                  <tr key={label} className="border-b border-line/60"><td className="py-2 pr-4">{label}</td>{systems.map((s) => <td key={s.label} className="py-2 pr-4 tabular-nums">{f(s)}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-sm text-muted">
          &ldquo;Not verified automatically&rdquo; means no Wikidata film or series matched the exact title. Several of these
          are real titles, so this is not a count of invented ones. Without Qloo, learners at the same level get almost the
          same list; with Qloo each list is personal. Comprende&apos;s later picks include labelled &ldquo;stretch&rdquo; titles on
          purpose, so the first five picks are the like-for-like comparison of level fit.
        </p>
      </section>

      <section className="mt-10 space-y-3">
        <h2 className="font-display text-2xl">Limits</h2>
        <ul className="list-disc space-y-2 pl-5 leading-relaxed">
          <li>Coverage counts words, not speech rate, accents, slang or visual help, which also affect understanding.</li>
          <li>Subtitles condense speech, and we use one subtitle file per title.</li>
          <li>Only titles in the open subtitle corpus can be measured; others are shown as &ldquo;difficulty not measured&rdquo;, never guessed.</li>
          <li>The vocabulary check is short (64 items), so the estimate is approximate. If a pick feels too hard, say so and the agent adjusts.</li>
        </ul>
      </section>

      <p className="mt-12 text-sm text-muted">
        Data: Qloo Insights API; Wikidata (CC0); OPUS OpenSubtitles v2024 (Lison &amp; Tiedemann 2016), from{" "}
        <a className="underline" href="https://www.opensubtitles.org/">opensubtitles.org</a>. Only word counts derived from subtitles are stored.
      </p>
    </main>
  );
}
