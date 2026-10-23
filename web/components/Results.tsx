"use client";

import type { ListenPick, Pick, RunResult } from "@/lib/api";
import TasteMap from "./TasteMap";

export type Feedback = "loved" | "not_for_me" | "too_hard";
export const pickKey = (p: Pick) => p.qloo_id ?? p.imdb ?? p.name;

const FEEDBACK: { kind: Feedback; label: string }[] = [
  { kind: "loved", label: "Loved it" },
  { kind: "too_hard", label: "Too hard" },
  { kind: "not_for_me", label: "Not for me" },
];

const SECTIONS: { key: Pick["bucket"]; title: string; blurb: string }[] = [
  { key: "watch_now", title: "Watch now", blurb: "You'd know at least 95% of the words: enough to follow and enjoy." },
  { key: "stretch", title: "A good stretch", blurb: "90–95% of the words. Doable with Spanish subtitles on." },
];

// Floor, never round: 94.9% must not display as 95% while sitting below the 95% threshold.
function pct(x: number) {
  return `${Math.floor(x * 100)}%`;
}

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

const FIT_BADGE: Record<string, { label: string; cls: string }> = {
  comfortable: { label: "Watch now", cls: "bg-good-soft text-good" },
  watchable: { label: "Watch now", cls: "bg-good-soft text-good" },
  stretch: { label: "Stretch", cls: "bg-warn-soft text-warn" },
  later: { label: "Later", cls: "bg-later-soft text-later" },
};

// Plain-language reading of Qloo's lift: affinity for this learner minus the title's typical affinity.
function tasteSentence(lift: number | null) {
  if (lift === null) return "Qloo matched it to your taste.";
  if (lift >= 0.05) return "Qloo says it fits your taste clearly more than it fits most people's.";
  if (lift > 0) return "Qloo says it fits your taste a little more than it fits most people's.";
  return "Qloo says it fits your taste about as well as it fits most people's: a broadly liked pick.";
}

function PickCard({ p, vocab, feedback, onFeedback }: {
  p: Pick;
  vocab: number;
  feedback?: Feedback;
  onFeedback: (p: Pick, f: Feedback | undefined) => void;
}) {
  const badge = p.fit ? FIT_BADGE[p.fit] : null;
  const watch = `https://www.justwatch.com/us/search?q=${encodeURIComponent(p.name_en || p.name)}`;
  return (
    <article className="rise flex gap-4 rounded-2xl border border-line bg-card p-3 shadow-sm sm:p-4">
      <div className="aspect-[2/3] w-24 shrink-0 overflow-hidden rounded-xl bg-line sm:w-28">
        {/* Posters come from Qloo's image CDN at a fixed small size; next/image would add nothing here. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {p.image ? <img src={p.image} alt={`Poster: ${p.name}`} className="h-full w-full object-cover" loading="lazy" /> : (
          <div className="grid h-full place-items-center p-2 text-center font-display text-sm text-muted">{p.name}</div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-col-reverse items-start gap-1 sm:flex-row sm:justify-between sm:gap-2">
          <h4 className="font-display text-xl leading-tight">{p.name}</h4>
          {badge && p.coverage !== null && (
            <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium tabular-nums ${badge.cls}`}>
              {badge.label} · {pct(p.coverage)}
            </span>
          )}
        </div>
        <p className="text-sm text-muted">
          {p.name_en && p.name_en !== p.name ? `${p.name_en} · ` : ""}{p.kind === "series" ? "Series" : "Film"}{p.year ? ` · ${p.year}` : ""}
        </p>
        {p.coverage !== null && (
          <>
            <p className="mt-2 text-sm">You&apos;d know <strong>{pct(p.coverage)}</strong> of the words</p>
            <CoverageBar coverage={p.coverage} />
          </>
        )}
        {p.because.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted">
            <span>Because you like</span>
            {p.because.map((b) => <span key={b} className="rounded-full bg-paper px-2 py-0.5 text-ink">{b}</span>)}
          </div>
        )}
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer text-muted hover:text-ink">Why this pick?</summary>
          <div className="mt-1 space-y-1 text-muted">
            <p>{tasteSentence(p.lift)}{p.affinity !== null ? ` (affinity ${p.affinity.toFixed(2)})` : ""}</p>
            {p.coverage !== null && (
              <p>
                From its subtitles, someone who knows about {vocab.toLocaleString()} words would recognise {pct(p.coverage)} of
                the dialogue.
                Comfortable listening starts around 95–98%.
              </p>
            )}
          </div>
        </details>
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          {p.qloo_id && FEEDBACK.map((f) => (
            <button key={f.kind} type="button" aria-pressed={feedback === f.kind}
              onClick={() => onFeedback(p, feedback === f.kind ? undefined : f.kind)}
              className={`rounded-full border px-2.5 py-1 text-xs transition ${feedback === f.kind
                ? "border-ink bg-ink text-paper" : "border-line text-muted hover:border-ink hover:text-ink"}`}>
              {f.label}
            </button>
          ))}
          <a href={watch} target="_blank" rel="noopener noreferrer"
            className="ml-auto text-xs text-muted underline hover:text-ink">Where to watch ↗</a>
        </div>
      </div>
    </article>
  );
}

function ListenLane({ artists, podcasts }: { artists: ListenPick[]; podcasts: ListenPick[] }) {
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
                {a.because.length > 0 ? `Because you like ${a.because.join(", ")}` : a.spanish_tags.join(", ")}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
  return (
    <div className="mt-10">
      <h3 className="font-display text-2xl">Listen in Spanish</h3>
      <p className="text-sm text-muted">
        Spanish-language and Latin {podcasts.length ? "artists and podcasts" : "artists"} Qloo matches to your taste, for
        listening practice. Found through Qloo genre tags; lyrics and episodes are not measured for difficulty.
      </p>
      {row(artists, "Music")}
      {row(podcasts, "Podcasts")}
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
  const changes = Object.keys(feedback).length;
  const b = result.buckets;
  const empty = SECTIONS.every((s) => b[s.key].length === 0) && !result.held_back;
  return (
    <section className="rise">
      <p className="text-sm font-medium uppercase tracking-wider text-accent">Your picks</p>
      <h2 className="font-display mt-1 text-3xl sm:text-4xl">Spanish you&apos;ll love, at your level</h2>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted">For fans of</span>
        {Object.values(result.favourites).map((f) => (
          <span key={f} className="rounded-full bg-ink px-3 py-1 text-paper">{f}</span>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm" role="group" aria-label="Change level">
        <span className="text-muted">At about <strong className="text-ink">{result.vocab_size.toLocaleString()}</strong> words. Try</span>
        {LEVELS.filter((v) => v !== result.vocab_size).map((v) => (
          <button key={v} type="button" onClick={() => onChangeLevel(v)}
            className="rounded-full border border-line bg-card px-3 py-1 hover:border-accent">
            {v.toLocaleString()} words
          </button>
        ))}
      </div>

      {note && <p className="rise mt-4 max-w-2xl rounded-2xl bg-good-soft p-4 text-sm">{note}</p>}

      {result.held_back && (
        <div className="rise mt-6 max-w-2xl rounded-3xl bg-later-soft p-5">
          <p className="text-sm font-medium uppercase tracking-wider text-later">Held back on purpose</p>
          <p className="font-display mt-1 text-2xl">{result.held_back.name}</p>
          <p className="mt-2">
            A strong match for your taste
            {result.held_back.because.length > 0 ? ` (because you like ${result.held_back.because.join(", ")})` : ""},
            but you&apos;d follow only <strong>{pct(result.held_back.coverage ?? 0)}</strong> of its words today.
            {result.held_back.words_to_go
              ? ` About ${result.held_back.words_to_go.toLocaleString()} more words and it reaches 95%.`
              : ""}{" "}Start with the picks below and come back to it.
          </p>
        </div>
      )}

      {result.map && <TasteMap titles={result.map.titles} grid={result.map.grid} vocab={result.vocab_size} />}

      {b.watch_now.length === 0 && b.stretch.length > 0 && (
        <p className="mt-8 max-w-2xl rounded-2xl bg-warn-soft p-4 text-sm">
          At about {result.vocab_size.toLocaleString()} words, no native title we measured is comfortable yet: these
          stretches are the closest. Watch with Spanish subtitles on, and use the slider above to see what opens up next.
        </p>
      )}

      {SECTIONS.map((s) => b[s.key].length > 0 && (
        <div key={s.key} className="mt-10">
          <h3 className="font-display text-2xl">{s.title}</h3>
          <p className="text-sm text-muted">{s.blurb}</p>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {b[s.key].map((p) => (
              <PickCard key={pickKey(p)} p={p} vocab={result.vocab_size} feedback={feedback[pickKey(p)]} onFeedback={onFeedback} />
            ))}
          </div>
        </div>
      ))}

      {result.qloo_unavailable && (
        <p className="mt-8 max-w-xl rounded-2xl bg-warn-soft p-5">
          Qloo&apos;s taste graph could not be reached just now, so we can&apos;t match titles to your taste. Please try
          again in a minute.
        </p>
      )}

      {empty && !result.qloo_unavailable && (
        <p className="mt-8 max-w-xl rounded-2xl bg-card p-5">
          None of the titles we measured fit both your taste and your level yet. Try adding a different favourite.
        </p>
      )}

      {result.listen && <ListenLane artists={result.listen.artists} podcasts={result.listen.podcasts} />}

      {b.unmeasured.length > 0 && (
        <div className="mt-10">
          <h3 className="font-display text-xl">Strong taste matches, difficulty not measured</h3>
          <p className="text-sm text-muted">Qloo matched these to your taste, but we have no subtitles to measure them yet.</p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {b.unmeasured.map((p) => (
              <li key={p.qloo_id ?? p.name} className="rounded-full border border-line bg-card px-3 py-1.5 text-sm">
                {p.name}{p.year ? <span className="text-muted"> · {p.year}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="mt-10 text-xs text-muted">
        {result.qloo_calls} Qloo API calls · {pct(result.measured_share)} of candidates had measured dialogue ·{" "}
        {result.mode === "agent" ? "planned by the agent" : "fixed plan (language model unavailable)"}
      </p>
      <button type="button" onClick={onRestart} className="mt-4 text-muted underline">Start over</button>

      {changes > 0 && (
        <div className="rise fixed inset-x-0 bottom-4 z-20 mx-auto flex w-[min(92%,32rem)] items-center justify-between gap-3 rounded-full bg-ink py-2 pl-5 pr-2 text-paper shadow-lg">
          <span className="text-sm">{changes} {changes === 1 ? "reaction" : "reactions"} noted</span>
          <button type="button" onClick={onUpdate} className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-accent-ink">
            Update my picks
          </button>
        </div>
      )}
    </section>
  );
}
