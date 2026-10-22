"use client";

import type { AgentEvent } from "@/lib/api";

export default function AgentRun({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const steps = events.filter((e) => e.type === "step" || e.type === "warning");
  return (
    <section className="rise max-w-xl" aria-live="polite">
      <h2 className="font-display text-3xl">{running ? "Finding your Spanish picks…" : "Done"}</h2>
      <ol className="mt-5 space-y-3">
        {steps.map((e, i) => {
          const last = i === steps.length - 1 && running;
          return (
            <li key={i} className="rise flex items-start gap-3">
              <span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs ${
                e.type === "warning" ? "bg-warn-soft text-warn" : last ? "bg-line" : "bg-good-soft text-good"}`}>
                {e.type === "warning" ? "!" : last ? <span className="h-2.5 w-2.5 animate-ping rounded-full bg-accent" /> : "✓"}
              </span>
              <span className={e.type === "warning" ? "text-warn" : ""}>{e.text}</span>
            </li>
          );
        })}
        {running && steps.length === 0 && <li className="text-muted">Starting the agent…</li>}
      </ol>
    </section>
  );
}
