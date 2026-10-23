"use client";

import { useEffect, useState } from "react";
import type { AgentEvent } from "@/lib/api";

// Where each step's data comes from, shown next to the step.
const SOURCE: Record<string, string> = {
  find_entity: "Qloo search",
  recommend_spanish_titles: "Qloo insights",
  score_measured_titles: "Qloo insights",
  recommend_spanish_audio: "Qloo tags",
  rank_for_learner: "Subtitles",
};
const EXPECTED_STEPS = 9; // three favourites, films, series, two scoring passes, music, ranking

export default function AgentRun({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const steps = events.filter((e) => e.type === "step" || e.type === "warning");
  const done = events.filter((e) => e.type === "step").length;
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!running) return;
    const t0 = Date.now();
    const id = setInterval(() => setSeconds(Math.round((Date.now() - t0) / 1000)), 500);
    return () => clearInterval(id);
  }, [running]);

  const progress = running ? Math.min(0.95, done / EXPECTED_STEPS) : 1;

  return (
    <section className="rise max-w-xl" aria-live="polite">
      <h2 className="font-display text-3xl">{running ? "Finding your Spanish picks…" : "What the agent did"}</h2>
      {running && (
        <>
          <p className="mt-2 text-sm text-muted">
            The agent asks Qloo for titles that match your taste, then checks each one&apos;s dialogue against your
            level. Usually 15–30 seconds. <span className="tabular-nums">{seconds}s</span>
          </p>
          <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-line" aria-hidden>
            <div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${progress * 100}%` }} />
          </div>
        </>
      )}
      <ol className="mt-5 space-y-3">
        {steps.map((e, i) => {
          const last = i === steps.length - 1 && running;
          const source = e.type === "step" ? SOURCE[e.tool] : null;
          return (
            <li key={i} className="rise flex items-start gap-3">
              <span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs ${
                e.type === "warning" ? "bg-warn-soft text-warn" : last ? "bg-line" : "bg-good-soft text-good"}`}>
                {e.type === "warning" ? "!" : last ? <span className="h-2.5 w-2.5 animate-ping rounded-full bg-accent" /> : "✓"}
              </span>
              <span className={`flex-1 ${e.type === "warning" ? "text-warn" : ""}`}>{e.text}</span>
              {source && <span className="shrink-0 rounded-full bg-paper px-2 py-0.5 text-xs text-muted">{source}</span>}
            </li>
          );
        })}
        {running && steps.length === 0 && <li className="text-muted">Starting the agent…</li>}
      </ol>
    </section>
  );
}
