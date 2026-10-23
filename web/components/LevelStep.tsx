"use client";

import { useEffect, useMemo, useState } from "react";
import { getVocabItems, type VocabItemsFile } from "@/lib/api";
import { estimateVocab, type VocabEstimate, type VocabItem } from "@/lib/comprehension";
import { useI18n } from "@/lib/i18n";

const PAGE = 16;
const PRESET_WORDS = [1000, 3000, 6000];

// Deterministic shuffle so real words and pseudowords are mixed the same way for everyone.
function shuffled<T>(xs: T[], seed = 11): T[] {
  const a = [...xs];
  let s = seed;
  for (let i = a.length - 1; i > 0; i--) {
    s = (s * 9301 + 49297) % 233280;
    const j = Math.floor((s / 233280) * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export default function LevelStep({ onDone, onBack }: {
  onDone: (vocab: number, how: "check" | "preset", estimate?: VocabEstimate) => void;
  onBack: () => void;
}) {
  const { t, f } = useI18n();
  const [data, setData] = useState<VocabItemsFile | null>(null);
  const [failed, setFailed] = useState(false);
  const [mode, setMode] = useState<"choose" | "check" | "result">("choose");
  const [page, setPage] = useState(0);
  const [known, setKnown] = useState<Record<string, boolean>>({});
  const [estimate, setEstimate] = useState<VocabEstimate | null>(null);

  useEffect(() => { getVocabItems().then(setData).catch(() => setFailed(true)); }, []);
  const items = useMemo<VocabItem[]>(() => (data ? shuffled(data.items) : []), [data]);
  const pages = Math.ceil(items.length / PAGE);
  const fakesMarked = items.filter((i) => !i.real && known[i.word]);

  const finish = () => {
    if (!data) return;
    const est = estimateVocab(items, known, data.bands);
    setEstimate(est);
    setMode("result");
  };

  return (
    <section className="rise">
      <p className="text-sm font-medium uppercase tracking-wider text-accent">{t.level.step}</p>
      <h2 className="font-display mt-1 text-3xl sm:text-4xl">{t.level.title}</h2>

      {mode === "choose" && (
        <>
          <p className="mt-2 max-w-xl text-muted">
            {t.level.lead}
          </p>
          <div className="mt-6 grid max-w-2xl gap-3 sm:grid-cols-2">
            <button type="button" disabled={!data} onClick={() => setMode("check")}
              className="rounded-2xl border-2 border-accent bg-card p-5 text-left shadow-sm transition hover:brightness-105 disabled:opacity-50 sm:row-span-3">
              <span className="font-display text-2xl">{t.level.checkTitle}</span>
              <span className="mt-2 block text-muted">
                {t.level.checkBody}
              </span>
              <span className="mt-4 inline-block rounded-full bg-accent px-4 py-1.5 text-sm font-medium text-accent-ink">
                {failed ? t.level.unavailable : data ? t.level.start : t.level.loading}
              </span>
            </button>
            {PRESET_WORDS.map((words, i) => (
              <button key={words} type="button" onClick={() => onDone(words, "preset")}
                className="rounded-2xl border border-line bg-card px-5 py-3.5 text-left hover:border-accent">
                <span className="font-medium">{t.level.presets[i][0]}</span>
                <span className="ml-2 text-sm text-muted">{t.level.presets[i][1]}</span>
              </button>
            ))}
          </div>
          <button type="button" onClick={onBack} className="mt-6 text-sm text-muted underline">{t.level.back}</button>
        </>
      )}

      {mode === "check" && (
        <>
          <p className="mt-2 max-w-xl text-muted">
            {t.level.checkLead(page + 1, pages)}
          </p>
          <div className="mt-6 grid max-w-2xl grid-cols-2 gap-2.5 sm:grid-cols-4">
            {items.slice(page * PAGE, (page + 1) * PAGE).map((i) => {
              const on = !!known[i.word];
              return (
                <button key={i.word} type="button" aria-pressed={on}
                  onClick={() => setKnown((k) => ({ ...k, [i.word]: !k[i.word] }))}
                  className={`rounded-xl border px-3 py-3.5 text-lg transition ${on
                    ? "border-good bg-good-soft font-medium text-good" : "border-line bg-card hover:border-ink"}`}>
                  {i.word}
                </button>
              );
            })}
          </div>
          <div className="mt-6 flex items-center gap-4">
            {page > 0 && <button type="button" onClick={() => setPage(page - 1)} className="text-muted underline">{t.level.previous}</button>}
            {page < pages - 1 ? (
              <button type="button" onClick={() => setPage(page + 1)}
                className="rounded-full bg-ink px-6 py-3 font-medium text-paper">{t.level.nextPage}</button>
            ) : (
              <button type="button" onClick={finish}
                className="rounded-full bg-accent px-6 py-3 font-medium text-accent-ink">{t.level.seeEstimate}</button>
            )}
            <div className="h-1.5 w-32 overflow-hidden rounded-full bg-line" aria-hidden>
              <div className="h-full bg-accent transition-all" style={{ width: `${((page + 1) / pages) * 100}%` }} />
            </div>
          </div>
        </>
      )}

      {mode === "result" && estimate && (
        <div className="rise mt-6 max-w-xl rounded-3xl border border-line bg-card p-6 shadow-sm">
          <p className="text-muted">{t.level.youKnow}</p>
          <p className="font-display text-5xl">{f.int(estimate.vocab_size)} <span className="text-2xl">{t.level.words}</span></p>
          <div className="mt-5 space-y-1.5" aria-label={t.level.bandsAria}>
            {estimate.bands.map((b) => (
              <div key={b.band[0]} className="flex items-center gap-3 text-sm">
                <span className="w-28 shrink-0 text-muted">{f.int(b.band[0])}–{f.int(b.band[1])}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-line">
                  <div className="h-full rounded-full bg-good" style={{ width: `${b.corrected * 100}%` }} />
                </div>
                <span className="w-12 text-right tabular-nums">{f.pct0(b.corrected)}</span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">{t.level.bandsNote}</p>
          {fakesMarked.length > 0 && (
            <p className="mt-4 rounded-xl bg-warn-soft p-3 text-sm">
              {t.level.fakes(fakesMarked.length, fakesMarked.map((w) => w.word).join(", "))}
              {!estimate.reliable && t.level.unreliable}
            </p>
          )}
          <div className="mt-6 flex flex-wrap gap-3">
            <button type="button" onClick={() => onDone(estimate.vocab_size, "check", estimate)}
              className="rounded-full bg-accent px-6 py-3 font-medium text-accent-ink">{t.level.findPicks}</button>
            <button type="button" onClick={() => { setKnown({}); setPage(0); setMode("check"); }}
              className="text-muted underline">{t.level.retake}</button>
          </div>
        </div>
      )}
    </section>
  );
}
