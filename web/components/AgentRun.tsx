"use client";

import { useEffect, useState } from "react";
import type { AgentEvent } from "@/lib/api";
import { useI18n, type Messages } from "@/lib/i18n";

// Where each step's data comes from, shown next to the step.
const SOURCE: Record<string, keyof Messages["run"]["source"]> = {
  find_entity: "search",
  recommend_spanish_titles: "insights",
  score_measured_titles: "insights",
  recommend_spanish_audio: "tags",
  rank_for_learner: "subtitles",
  explain_picks: "explainer",
};
const EXPECTED_STEPS = 9; // three favourites, films, series, two scoring passes, music, ranking

// The backend sends English text plus structured data; rebuild the sentence in the chosen language.
function describe(e: AgentEvent, t: Messages, int: (x: number) => string): string {
  if (e.type !== "step" && e.type !== "warning") return "";
  const d = e.data;
  if (!d) return e.text;
  const series = d.kind === "tv_show";
  if (e.type === "step") {
    switch (e.tool) {
      case "find_entity": return t.run.find(String(d.query));
      case "recommend_spanish_titles": return t.run.recommend(series);
      case "score_measured_titles": return t.run.score(series, int(Number(d.count)));
      case "recommend_spanish_audio": return t.run.music;
      case "rank_for_learner": return t.run.rank(int(Number(d.vocab)));
      case "explain_picks": return t.run.explain;
    }
    return e.text;
  }
  switch (e.code) {
    case "qloo": return t.run.qloo(String(d.code));
    case "fallback": return t.run.fallback();
    case "model_slow": return t.run.modelSlow(String(d.from), String(d.to));
    case "model_busy": return t.run.modelBusy(String(d.from), String(d.to));
  }
  return e.text;
}

export default function AgentRun({ events, running, level = 1 }: { events: AgentEvent[]; running: boolean; level?: 1 | 2 }) {
  const { t, f } = useI18n();
  // Model failover is plumbing, not something a learner needs to read.
  const steps = events.filter((e) => e.type === "step"
    || (e.type === "warning" && e.code !== "model_busy" && e.code !== "model_slow"));
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
    <section className="rise max-w-xl">
      {level === 1
        ? <h1 className="font-display text-3xl">{running ? t.run.running : t.run.done}</h1>
        : <h2 className="font-display text-3xl">{running ? t.run.running : t.run.done}</h2>}
      {running && (
        <>
          <p className="mt-2 text-sm text-muted">
            {t.run.explainer} <span className="tabular-nums" aria-hidden>{seconds}&nbsp;s</span>
          </p>
          <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-line" aria-hidden>
            <div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${progress * 100}%` }} />
          </div>
        </>
      )}
      <ol className="mt-5 space-y-3" aria-live={running ? "polite" : "off"}>
        {steps.map((e, i) => {
          const last = i === steps.length - 1 && running;
          const source = e.type === "step" && SOURCE[e.tool] ? t.run.source[SOURCE[e.tool]] : null;
          return (
            <li key={i} className="rise flex items-start gap-3">
              <span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs ${
                e.type === "warning" ? "bg-warn-soft text-warn" : last ? "bg-line" : "bg-good-soft text-good"}`}>
                {e.type === "warning" ? "!" : last ? <span className="h-2.5 w-2.5 animate-ping rounded-full bg-accent" /> : "✓"}
              </span>
              <span className={`flex-1 ${e.type === "warning" ? "text-warn" : ""}`}>{describe(e, t, f.int)}</span>
              {source && <span className="shrink-0 rounded-full bg-paper px-2 py-0.5 text-xs text-muted">{source}</span>}
            </li>
          );
        })}
        {running && steps.length === 0 && <li className="text-muted">{t.run.starting}</li>}
      </ol>
    </section>
  );
}
