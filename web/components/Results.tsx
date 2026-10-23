"use client";

import type { ListenPick, Pick, RunResult } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import TasteMap from "./TasteMap";

export type Feedback = "loved" | "not_for_me" | "too_hard";
export const pickKey = (p: Pick) => p.qloo_id ?? p.imdb ?? p.name;

const FEEDBACK: Feedback[] = ["loved", "too_hard", "not_for_me"];
const SECTIONS: Pick["bucket"][] = ["watch_now", "stretch"];

function CoverageBar({ coverage }: { coverage: number }) {
  // Scale 80–100% so the thresholds that matter (95%, 98%) are visible.
  const pos = (v: number) => `${Math.max(0, Math.min(1, (v - 0.8) / 0.2)) * 100}%`;
  const tone = coverage >= 0.95 ? "bg-good" : coverage >= 0.9 ? "bg-warn" : "bg-later";
  return (
    <div className="relative mt-2 h-2 rounded-full bg-line" aria-hidden>
      <div className={`h-full rounded-full ${tone}`} style={{ width: pos(coverage) }} />
      <div className="absolute -top-1 h-4 w-px bg-ink/40" style={{ left: pos(0.95) }} />
      <div className="absolute -top-1 h-4 w-px bg-ink/40" style={{ left: pos(0.98) }} />
    </div>
  );
}

const FIT_CLASS: Record<string, string> = {
  comfortable: "bg-good-soft text-good",
  watchable: "bg-good-soft text-good",
  stretch: "bg-warn-soft text-warn",
  later: "bg-later-soft text-later",
};

const JUSTWATCH: Record<string, string> = { en: "us", fr: "fr", es: "es" };

function PickCard({ p, vocab, blend, feedback, onFeedback }: {
  p: Pick;
  vocab: number;
  blend: boolean;
  feedback?: Feedback;
  onFeedback: (p: Pick, f: Feedback | undefined) => void;
}) {
  const { t, f, lang } = useI18n();
  // Floor, never round: 94.9% must not display as 95% while sitting below the 95% threshold.
  const pct = f.pctFloor;
  // Plain-language reading of Qloo's lift: affinity for this learner minus the title's typical affinity.
  const taste = p.lift === null ? t.card.tasteNone
    : p.lift >= 0.05 ? t.card.tasteClear : p.lift > 0 ? t.card.tasteBit : t.card.tasteSame;
  const badge = p.fit && FIT_CLASS[p.fit] ? { label: t.card.fit[p.fit], cls: FIT_CLASS[p.fit] } : null;
  // English title for the US catalogue, the original title elsewhere.
  const watch = `https://www.justwatch.com/${JUSTWATCH[lang]}/search?q=${encodeURIComponent(
    (lang === "en" && p.name_en) || p.name)}`;
  return (
    <article className="rise flex gap-4 rounded-2xl border border-line bg-card p-3 shadow-sm sm:p-4">
      <div className="aspect-[2/3] w-24 shrink-0 overflow-hidden rounded-xl bg-line sm:w-28">
        {/* Posters come from Qloo's image CDN at a fixed small size; next/image would add nothing here. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {p.image ? <img src={p.image} alt={t.card.poster(p.name)} className="h-full w-full object-cover" loading="lazy" /> : (
          <div className="grid h-full place-items-center p-2 text-center font-display text-sm text-muted">{p.name}</div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-col-reverse items-start gap-1 sm:flex-row sm:justify-between sm:gap-2">
          <h4 className="font-display text-xl leading-tight" lang="es">{p.name}</h4>
          {badge && p.coverage !== null && (
            <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium tabular-nums ${badge.cls}`}>
              {badge.label} · {pct(p.coverage)}
            </span>
          )}
        </div>
        <p className="text-sm text-muted">
          {p.name_en && p.name_en.toLowerCase() !== p.name.toLowerCase() ? `${p.name_en} · ` : ""}{p.kind === "series" ? t.card.series : t.card.film}{p.year ? ` · ${p.year}` : ""}
        </p>
        {p.coverage !== null && (
          <>
            <p className="mt-2 text-sm">{t.card.youdKnow(pct(p.coverage))}</p>
            <CoverageBar coverage={p.coverage} />
          </>
        )}
        {p.because.length > 0 ? (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted">
            <span>{t.res.becauseYouLike}</span>
            {p.because.map((b) => <span key={b} className="rounded-full bg-paper px-2 py-0.5 text-ink">{b}</span>)}
          </div>
        ) : blend && <p className="mt-2 text-xs text-muted">{t.res.blend}</p>}
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer text-muted hover:text-ink">{t.card.why}</summary>
          <div className="mt-1 space-y-1 text-muted">
            <p>
              {taste}
              {p.affinity !== null
                ? t.card.affinity(p.affinity.toLocaleString(lang, { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
                : ""}
            </p>
            {p.coverage !== null && <p>{t.card.coverage(f.int(vocab), pct(p.coverage))}</p>}
          </div>
        </details>
        <div className="mt-3 flex flex-wrap items-center gap-1.5" role="group" aria-label={t.card.feedbackAria(p.name)}>
          {p.qloo_id && FEEDBACK.map((k) => (
            <button key={k} type="button" aria-pressed={feedback === k}
              onClick={() => onFeedback(p, feedback === k ? undefined : k)}
              className={`min-h-9 rounded-full border px-3 py-1.5 text-xs transition ${feedback === k
                ? "border-ink bg-ink text-paper" : "border-line text-muted hover:border-ink hover:text-ink"}`}>
              {t.card.feedback[k]}
            </button>
          ))}
          <a href={watch} target="_blank" rel="noopener noreferrer"
            className="ml-auto py-2 text-xs text-muted underline hover:text-ink">
            {t.card.watch}<span className="sr-only"> {t.card.newTab}</span>
          </a>
        </div>
      </div>
    </article>
  );
}

function ListenLane({ artists, podcasts, blend }: { artists: ListenPick[]; podcasts: ListenPick[]; blend: boolean }) {
  const { t } = useI18n();
  if (artists.length + podcasts.length === 0) return null;
  const row = (items: ListenPick[], label: string) => items.length > 0 && (
    <div className="mt-4">
      <p className="text-sm font-medium text-muted">{label}</p>
      <ul className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((a) => (
          <li key={a.qloo_id} className="flex min-w-0 items-center gap-3 rounded-2xl border border-line bg-card p-3">
            <div className={`h-12 w-12 shrink-0 overflow-hidden bg-line ${a.kind === "artist" ? "rounded-full" : "rounded-lg"}`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {a.image ? <img src={a.image} alt="" className="h-full w-full object-cover" loading="lazy" /> : null}
            </div>
            <div className="min-w-0">
              <a href={`https://open.spotify.com/search/${encodeURIComponent(a.name)}`} target="_blank"
                rel="noopener noreferrer" className="block truncate font-medium hover:underline">{a.name}</a>
              <p className="truncate text-xs text-muted">
                {a.because.length > 0 ? `${t.res.becauseYouLike} ${a.because.join(", ")}` : blend ? t.res.blend : a.spanish_tags.join(", ")}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
  return (
    <div className="mt-10">
      <h3 className="font-display text-2xl">{t.res.listenTitle}</h3>
      <p className="text-sm text-muted">{t.res.listenBlurb}</p>
      {row(artists, t.res.music)}
      {row(podcasts, t.fav.kinds.podcast)}
    </div>
  );
}

const LEVELS = [1000, 3000, 6000];

export default function Results({ result, onRestart, onChangeLevel, feedback, onFeedback, onUpdate, note }: {
  result: RunResult;
  onRestart: () => void;
  onChangeLevel: (vocab: number) => void;
  feedback: Record<string, Feedback>;
  onFeedback: (p: Pick, f: Feedback | undefined) => void;
  onUpdate: () => void;
  note: string | null;
}) {
  const { t, f } = useI18n();
  const pct = f.pctFloor;
  const changes = Object.keys(feedback).length;
  const b = result.buckets;
  const held = result.held_back;
  const blend = Object.keys(result.favourites).length > 1;
  const empty = SECTIONS.every((s) => b[s].length === 0) && !held;
  return (
    <section className="rise">
      <p className="text-sm font-medium uppercase tracking-wider text-accent">{t.res.eyebrow}</p>
      <h2 className="font-display mt-1 text-3xl sm:text-4xl">{t.res.title}</h2>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted">{t.res.fansOf}</span>
        {Object.values(result.favourites).map((name) => (
          <span key={name} className="rounded-full bg-ink px-3 py-1 text-paper">{name}</span>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm" role="group" aria-label={t.res.changeLevel}>
        <span className="text-muted">{t.res.atAbout(f.int(result.vocab_size))}</span>
        {LEVELS.filter((v) => v !== result.vocab_size).map((v) => (
          <button key={v} type="button" onClick={() => onChangeLevel(v)}
            className="rounded-full border border-line bg-card px-3 py-1 hover:border-accent">
            {t.res.nWords(f.int(v))}
          </button>
        ))}
      </div>

      {note && <p className="rise mt-4 max-w-2xl rounded-2xl bg-good-soft p-4 text-sm">{note}</p>}

      {held && (
        <div className="rise mt-6 max-w-2xl rounded-3xl bg-later-soft p-5">
          <p className="text-sm font-medium uppercase tracking-wider text-later">{t.res.heldEyebrow}</p>
          <p className="font-display mt-1 text-2xl">{held.name}</p>
          <p className="mt-2">
            {t.res.held(held.because.join(", "), pct(held.coverage ?? 0), held.words_to_go ? f.int(held.words_to_go) : null)}
          </p>
        </div>
      )}

      {result.map && <TasteMap titles={result.map.titles} grid={result.map.grid} vocab={result.vocab_size} />}

      {b.watch_now.length === 0 && b.stretch.length > 0 && (
        <p className="mt-8 max-w-2xl rounded-2xl bg-warn-soft p-4 text-sm">{t.res.beginner(f.int(result.vocab_size))}</p>
      )}

      {SECTIONS.map((s) => b[s].length > 0 && (
        <div key={s} className="mt-10">
          <h3 className="font-display text-2xl">{t.res.sections[s][0]}</h3>
          <p className="text-sm text-muted">{t.res.sections[s][1]}</p>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {b[s].map((p) => (
              <PickCard key={pickKey(p)} p={p} vocab={result.vocab_size} blend={blend} feedback={feedback[pickKey(p)]} onFeedback={onFeedback} />
            ))}
          </div>
        </div>
      ))}

      {result.qloo_unavailable && <p className="mt-8 max-w-xl rounded-2xl bg-warn-soft p-5">{t.res.qlooDown}</p>}

      {empty && !result.qloo_unavailable && <p className="mt-8 max-w-xl rounded-2xl bg-card p-5">{t.res.empty}</p>}

      {result.listen && <ListenLane artists={result.listen.artists} podcasts={result.listen.podcasts} blend={blend} />}

      {b.unmeasured.length > 0 && (
        <div className="mt-10">
          <h3 className="font-display text-xl">{t.res.unmeasuredTitle}</h3>
          <p className="text-sm text-muted">{t.res.unmeasuredBlurb}</p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {b.unmeasured.map((p) => (
              <li key={p.qloo_id ?? p.name} className="rounded-full border border-line bg-card px-3 py-1.5 text-sm">
                {p.name}{p.year ? <span className="text-muted"> · {p.year}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="mt-10 text-xs text-muted">{t.res.stats(result.qloo_calls, pct(result.measured_share), result.mode === "agent")}</p>
      <button type="button" onClick={onRestart} className="mt-4 text-muted underline">{t.res.restart}</button>

      {changes > 0 && (
        <div className="rise fixed inset-x-0 bottom-4 z-20 mx-auto flex w-[min(92%,32rem)] items-center justify-between gap-3 rounded-full bg-ink py-2 pl-5 pr-2 text-paper shadow-lg">
          <span className="text-sm" role="status">{t.res.reactions(changes)}</span>
          <button type="button" onClick={onUpdate} className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-accent-ink">
            {t.res.update}
          </button>
        </div>
      )}
    </section>
  );
}
