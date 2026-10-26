"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

// A short looping demo of what the app does, in three steps: what you love, what the agent does, what
// you get. It replays a real example run (Breaking Bad + Bad Bunny + The Legend of Zelda at ~3,000 words,
// coverage figures from the catalog) and is labelled as an example. Clicking it runs that example live.
// With reduced motion it shows the last step, still.
const STEP_MS = 3400;
const FAVS = ["Breaking Bad", "Bad Bunny", "The Legend of Zelda"];

export default function HeroPreview({ onTry }: { onTry: () => void }) {
  const { t, f } = useI18n();
  const [step, setStep] = useState(2);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    setStep(0);
    if (paused) return;
    const id = setInterval(() => setStep((s) => (s + 1) % 3), STEP_MS);
    return () => clearInterval(id);
  }, [paused]);

  const p = t.preview;
  return (
    <button type="button" onClick={onTry} onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)} onBlur={() => setPaused(false)} aria-label={p.aria}
      className="group relative block w-full rounded-3xl border border-line bg-card p-5 text-left shadow-sm transition hover:border-accent">
      <div className="flex items-center justify-between gap-2 text-xs uppercase tracking-wider text-muted">
        <span>{p.label}</span>
        <span className="flex gap-1.5" aria-hidden>
          {[0, 1, 2].map((i) => (
            <span key={i} className={`h-1.5 w-5 rounded-full transition-colors ${i === step ? "bg-accent" : "bg-line"}`} />
          ))}
        </span>
      </div>

      {/* fixed height so the page does not jump between steps */}
      <div className="relative mt-4 h-64 overflow-hidden" aria-hidden>
        {step === 0 && (
          <div key="s0" className="rise">
            <p className="font-display text-xl">{p.s1}</p>
            <ul className="mt-4 flex flex-wrap gap-2">
              {FAVS.map((name, i) => (
                <li key={name} className="rise rounded-full bg-ink px-4 py-2 text-paper"
                  style={{ animationDelay: `${250 + i * 350}ms` }}>{name}</li>
              ))}
            </ul>
            <p className="rise mt-5 text-sm text-muted" style={{ animationDelay: "1400ms" }}>{p.s1sub}</p>
          </div>
        )}
        {step === 1 && (
          <div key="s1" className="rise">
            <p className="font-display text-xl">{p.s2}</p>
            <ol className="mt-4 space-y-3 text-sm">
              {p.s2steps.map(([source, text], i) => (
                <li key={source} className="rise flex items-start gap-3" style={{ animationDelay: `${200 + i * 700}ms` }}>
                  <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-good-soft text-[11px] text-good">✓</span>
                  <span className="flex-1">{text}</span>
                  <span className="shrink-0 rounded-full bg-paper px-2 py-0.5 text-xs text-muted">{source}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
        {step === 2 && (
          <div key="s2" className="rise">
            <p className="font-display text-xl">{p.s3}</p>
            <ul className="mt-3 space-y-3 text-sm">
              <li className="rounded-2xl border border-line p-3">
                <div className="flex items-center justify-between gap-2">
                  <strong className="font-display text-base" lang="es">Celda 211</strong>
                  <span className="rounded-full bg-good-soft px-2 py-0.5 text-xs font-medium text-good">{p.watchNow} · {f.pct0(0.95)}</span>
                </div>
                <p className="mt-1 text-muted">{p.reason}</p>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line">
                  <div className="h-full rounded-full bg-good transition-[width] duration-1000" style={{ width: "77%" }} />
                </div>
              </li>
              <li className="rise rounded-2xl bg-later-soft p-3" style={{ animationDelay: "700ms" }}>
                <div className="flex items-center justify-between gap-2">
                  <strong className="font-display text-base" lang="es">Balada triste de trompeta</strong>
                  <span className="rounded-full bg-card px-2 py-0.5 text-xs font-medium text-later">{p.heldBack} · {f.pct0(0.89)}</span>
                </div>
                <p className="mt-1">{p.heldWhy}</p>
              </li>
            </ul>
          </div>
        )}
      </div>

      <p className="mt-3 text-sm font-medium text-accent group-hover:underline">{p.cta}</p>
    </button>
  );
}
