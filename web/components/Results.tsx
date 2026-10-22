"use client";

import type { Pick, RunResult } from "@/lib/api";

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

function PickCard({ p, feedback, onFeedback }: {
  p: Pick;
  feedback?: Feedback;
  onFeedback: (p: Pick, f: Feedback | undefined) => void;
}) {
  return (
    <article className="rise flex gap-4 rounded-2xl border border-line bg-card p-4 shadow-sm">
      <div className="h-32 w-[88px] shrink-0 overflow-hidden rounded-lg bg-line">
        {/* Posters come from Qloo's image CDN at a fixed small size; next/image would add nothing here. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {p.image ? <img src={p.image} alt="" className="h-full w-full object-cover" loading="lazy" /> : null}
      </div>
      <div className="min-w-0 flex-1">
        <h4 className="font-display text-xl leading-tight">{p.name}</h4>
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
          <p className="mt-2 text-sm text-muted">Because you like <span className="text-ink">{p.because.join(", ")}</span></p>
        )}
        {p.affinity !== null && <p className="mt-1 text-xs text-muted">Qloo taste affinity {p.affinity.toFixed(2)}</p>}
        {p.qloo_id && (
          <div className="mt-3 flex flex-wrap gap-1.5" role="group" aria-label={`Feedback on ${p.name}`}>
            {FEEDBACK.map((f) => (
              <button key={f.kind} type="button" aria-pressed={feedback === f.kind}
                onClick={() => onFeedback(p, feedback === f.kind ? undefined : f.kind)}
                className={`rounded-full border px-2.5 py-1 text-xs transition ${feedback === f.kind
                  ? "border-ink bg-ink text-paper" : "border-line text-muted hover:border-ink hover:text-ink"}`}>
                {f.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

export default function Results({ result, onRestart, feedback, onFeedback, onUpdate, note }: {
  result: RunResult;
  onRestart: () => void;
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
      <p className="mt-2 text-muted">
        Based on about {result.vocab_size.toLocaleString()} known words and {Object.keys(result.favourites).length} favourites.
      </p>

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

      {SECTIONS.map((s) => b[s.key].length > 0 && (
        <div key={s.key} className="mt-10">
          <h3 className="font-display text-2xl">{s.title}</h3>
          <p className="text-sm text-muted">{s.blurb}</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {b[s.key].map((p) => (
              <PickCard key={pickKey(p)} p={p} feedback={feedback[pickKey(p)]} onFeedback={onFeedback} />
            ))}
          </div>
        </div>
      ))}

      {empty && (
        <p className="mt-8 max-w-xl rounded-2xl bg-card p-5">
          None of the titles we measured fit both your taste and your level yet. Try adding a different favourite.
        </p>
      )}

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
