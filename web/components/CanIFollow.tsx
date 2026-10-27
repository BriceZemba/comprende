"use client";

import { useEffect, useState } from "react";
import { coverageAt, fitFor } from "@/lib/comprehension";
import { useI18n } from "@/lib/i18n";

interface Title {
  imdb: string;
  qloo_id: string | null;
  title_es: string | null;
  title_en: string | null;
  year: number | null;
  kind: "film" | "series";
  curve: number[];
  vocab_for_95: number | null;
}

const TRY = ["La casa de papel", "El hoyo", "Roma", "Relatos salvajes"];
const MIN = 500, MAX = 12000, STEP = 250;
const TONE = { good: ["text-good", "bg-good"], warn: ["text-warn", "bg-warn"], later: ["text-later", "bg-later"] };

// "Can I follow it?": type any Spanish title and see how much of its dialogue you would understand at your
// level, and how many more words you need to drop the subtitles. Our subtitle measurements only: no Qloo
// call, no model. The level starts from the learner's saved one, or ~3,000 words, and can be moved.
export default function CanIFollow({ vocab: start, onCheck }: { vocab: number; onCheck: () => void }) {
  const { t, f } = useI18n();
  const c = t.check;
  const [q, setQ] = useState("");
  const [vocab, setVocab] = useState(start);
  const [found, setFound] = useState<{ grid: number[]; titles: Title[] } | null>(null);
  const [pick, setPick] = useState(0);
  useEffect(() => setVocab(start), [start]);

  useEffect(() => {
    const query = q.trim();
    if (query.length < 2) { setFound(null); return; }
    const ctl = new AbortController();
    const id = setTimeout(() => {
      fetch(`/api/title?q=${encodeURIComponent(query)}`, { signal: ctl.signal })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => { if (d) { setFound(d); setPick(0); } })
        .catch(() => { /* typing on: an older request was aborted */ });
    }, 220);
    return () => { clearTimeout(id); ctl.abort(); };
  }, [q]);

  const title = found?.titles[pick];
  const cov = title && found ? coverageAt(found.grid, title.curve, vocab) : null;
  const fit = cov != null ? fitFor(cov) : null;
  const toGo = title?.vocab_for_95 != null ? Math.max(0, title.vocab_for_95 - vocab) : null;
  const tone = fit === "comfortable" || fit === "watchable" ? "good" : fit === "stretch" ? "warn" : "later";
  const verdict = !title || cov == null ? null
    : fit === "comfortable" || fit === "watchable" ? c.go
    : title.vocab_for_95 == null ? c.veryHard
    : fit === "stretch" ? c.stretch(f.int(toGo ?? 0)) : c.later(f.int(toGo ?? 0));

  return (
    <section id="check" aria-labelledby="check-title" className="mt-20 scroll-mt-6 rounded-[1.75rem] border border-line bg-card p-5 shadow-sm sm:p-8">
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_1.15fr] lg:gap-12">
        <div>
          <h2 id="check-title" className="font-display text-3xl sm:text-4xl">{c.title}</h2>
          <p className="mt-3 text-muted">{c.lead}</p>
          <label htmlFor="check-q" className="mt-6 block text-sm font-medium">{c.label}</label>
          <input id="check-q" type="search" value={q} onChange={(e) => setQ(e.target.value)} autoComplete="off"
            placeholder={c.placeholder} maxLength={80}
            className="mt-2 w-full rounded-2xl border border-line bg-paper px-4 py-3 text-lg outline-none focus:border-accent" />
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted">{c.try}</span>
            {TRY.map((name) => (
              <button key={name} type="button" onClick={() => setQ(name)} lang="es"
                className="rounded-full border border-line px-3 py-1 hover:border-accent">{name}</button>
            ))}
          </div>
          <label htmlFor="check-v" className="mt-6 flex items-baseline justify-between gap-3 text-sm">
            <span className="font-medium">{c.vocab(f.int(vocab))}</span>
            <button type="button" onClick={onCheck} className="text-accent underline">{c.checkLink}</button>
          </label>
          <input id="check-v" type="range" min={MIN} max={MAX} step={STEP} value={vocab}
            onChange={(e) => setVocab(Number(e.target.value))} className="mt-2 w-full accent-[var(--accent)]" />
        </div>

        <div aria-live="polite" className="min-h-[15rem]">
          {!found && (
            <div className="grid h-full place-items-center rounded-2xl border border-dashed border-line p-6 text-center text-muted">
              <p>{c.empty}</p>
            </div>
          )}
          {found && !title && (
            <div className="rounded-2xl bg-paper p-6">
              <p className="font-medium">{c.none(q.trim())}</p>
              <p className="mt-2 text-sm text-muted">{c.noneWhy}</p>
            </div>
          )}
          {title && cov != null && (
            <div key={title.imdb} className="rise flex gap-4 rounded-2xl bg-paper p-4 sm:gap-5 sm:p-5">
              {title.qloo_id && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={`https://images.qloo.com/i/${title.qloo_id}-420x-auto.jpg`} alt=""
                  onError={(e) => { e.currentTarget.style.display = "none"; }}
                  className="h-40 w-28 shrink-0 rounded-xl bg-line object-cover sm:h-48 sm:w-32" />
              )}
              <div className="min-w-0 flex-1">
                <p className="font-display text-2xl leading-tight" lang="es">{title.title_es ?? title.title_en}</p>
                <p className="mt-0.5 text-sm text-muted">
                  {[title.title_en && title.title_en !== title.title_es ? title.title_en : null, title.year,
                    title.kind === "series" ? c.series : c.film].filter(Boolean).join(" · ")}
                </p>
                <p className="mt-4 text-sm text-muted">{c.youd(f.int(vocab))}</p>
                <p className={`font-display text-5xl tabular-nums ${TONE[tone][0]}`}>{f.pctFloor(cov)}</p>
                <div className="relative mt-2 h-2.5 rounded-full bg-line">
                  <div className={`h-full rounded-full ${TONE[tone][1]} transition-[width] duration-300`} style={{ width: `${cov * 100}%` }} />
                  <span className="absolute -top-1 h-[18px] w-0.5 rounded bg-ink/60" style={{ left: "95%" }} aria-hidden />
                </div>
                <p className="mt-1 text-right text-[11px] text-muted">{c.mark}</p>
                <p className="mt-2 font-medium">{verdict}</p>
              </div>
            </div>
          )}
          {found && found.titles.length > 1 && (
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted">{c.others}</span>
              {found.titles.map((x, i) => i !== pick && (
                <button key={x.imdb} type="button" onClick={() => setPick(i)} lang="es"
                  className="rounded-full border border-line px-3 py-1 hover:border-accent">
                  {x.title_es ?? x.title_en}{x.year ? ` (${x.year})` : ""}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
