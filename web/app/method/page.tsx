"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { useI18n } from "@/lib/i18n";

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

// Table rows, in the order of t.method.rows.
const ROWS: ((s: SystemSummary) => number | null)[] = [
  (s) => s.spanish_original, (s) => s.not_spanish, (s) => s.unverified, (s) => s.distinct_share, (s) => s.fit_n,
  (s) => s.fit_95, (s) => s.fit_below_90, (s) => s.first5_n, (s) => s.first5_95, (s) => s.first5_below_90,
];
const COUNT_ROWS = new Set([4, 7]);

export default function Method() {
  const { t, f } = useI18n();
  // One decimal, same as eval/results/report.md and data/validation_es.md.
  const pct = f.pct1;
  const n = f.int;
  const [data, setData] = useState<{ validation: Validation | null; evaluation: Record<string, SystemSummary> | null } | null>(null);
  useEffect(() => { fetch("/api/method").then((r) => r.json()).then(setData).catch(() => setData({ validation: null, evaluation: null })); }, []);
  const v = data?.validation;
  const systems = data?.evaluation ? Object.entries(data.evaluation) : [];
  const opensubs = <a className="underline" href="https://www.opensubtitles.org/">opensubtitles.org</a>;

  return (
    <main className="mx-auto max-w-3xl px-4 pb-24 sm:px-8">
      <Header nav={<Link href="/" className="hover:text-ink">{t.nav.tryIt}</Link>} />
      <h1 className="font-display text-4xl sm:text-5xl">{t.method.title}</h1>

      <section className="mt-10 space-y-4 leading-relaxed">
        <h2 className="font-display text-2xl">{t.method.tasteT}</h2>
        <p>{t.method.taste}</p>
      </section>

      <section className="mt-10 space-y-4 leading-relaxed">
        <h2 className="font-display text-2xl">{t.method.diffT}</h2>
        <p>{t.method.diff1}</p>
        <p>{t.method.diff2}</p>
        <p>{t.method.diff3}</p>
      </section>

      <section className="mt-10 space-y-4">
        <h2 className="font-display text-2xl">{t.method.checkT}</h2>
        {v ? (
          <ul className="list-disc space-y-2 pl-5 leading-relaxed">
            <li>{t.method.check1(n(v.titles), n(v.median_vocab_for_95), n(v.p25_vocab_for_95), n(v.p75_vocab_for_95), n(v.median_vocab_for_98))}</li>
            <li>{t.method.check2(pct(v.median_coverage_at_1000), pct(v.median_coverage_at_3000))}</li>
            {v.genre_check && (
              <li>{t.method.check3(pct(v.genre_check.animation_family), pct(v.genre_check.drama), v.genre_check.animation_family_titles)}</li>
            )}
          </ul>
        ) : <p className="text-muted">{t.method.loading}</p>}
      </section>

      <section className="mt-10 space-y-4">
        <h2 className="font-display text-2xl">{t.method.compareT}</h2>
        <p className="leading-relaxed">{t.method.compare}</p>
        {systems.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line">
                  <th className="py-2 pr-4">{t.method.measure}</th>
                  {systems.map(([key, s]) => <th key={key} className="py-2 pr-4">{t.method.systems[key] ?? s.label}</th>)}
                </tr>
              </thead>
              <tbody>
                {t.method.rows.map((label, i) => (
                  <tr key={i} className="border-b border-line/60">
                    <td className="py-2 pr-4">{label}</td>
                    {systems.map(([key, s]) => {
                      const val = ROWS[i](s);
                      return <td key={key} className="py-2 pr-4 tabular-nums">{COUNT_ROWS.has(i) ? n(val ?? 0) : pct(val)}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-sm text-muted">{t.method.compareNote}</p>
      </section>

      <section className="mt-10 space-y-3">
        <h2 className="font-display text-2xl">{t.method.limitsT}</h2>
        <ul className="list-disc space-y-2 pl-5 leading-relaxed">
          {t.method.limits.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </section>

      <p className="mt-12 text-sm text-muted">{t.method.data(opensubs)}</p>
    </main>
  );
}
