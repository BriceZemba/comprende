"use client";

import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { useI18n } from "@/lib/i18n";

// A looping demo of what the app does, in three steps: what you love, what the agent does, what you get.
// Everything in it comes from the recorded example run (data/example_run.json: Breaking Bad + Bad Bunny +
// The Legend of Zelda at ~3,000 words): one title from each list (watch now, a good stretch, later), their
// posters from Qloo, their coverage, the words still to learn and the explainer's reason. The tabs jump
// between steps; hovering pauses. With reduced motion it shows the last step, still.
const STEP_MS = 4200;
const MEASURED = 1464;
const POSTER = "https://images.qloo.com/i/";
const PICKS = [
  { name: "Hogar", year: 2020, coverage: 0.9532, tone: "good", image: `${POSTER}755051F8-D604-4E93-89E0-04897E4B93F7-420x-auto.jpg` },
  { name: "El hoyo", year: 2019, coverage: 0.9381, tone: "warn", image: `${POSTER}985F6F9D-FE97-41AF-BDC7-A2EFC513BEA7-420x-auto.jpg` },
  { name: "La sociedad de la nieve", year: 2023, coverage: 0.8998, tone: "later", image: `${POSTER}D3939768-1816-4F23-9AD7-E6E27254A321-420x-auto.jpg` },
] as const;
const LATER_TO_GO = 3500; // words to learn before La sociedad de la nieve reaches 95%
const TONE = {
  good: { bar: "bg-good", badge: "bg-good text-paper" },
  warn: { bar: "bg-warn", badge: "bg-warn text-paper" },
  later: { bar: "bg-later", badge: "bg-later text-paper" },
};

const ICONS: ReactNode[] = [
  // series: a screen
  <path key="tv" d="M3 6h18v11H3zM8 21h8M12 17v4" />,
  // artist: a note
  <path key="note" d="M9 18V5l11-2v13M9 18a3 3 0 1 1-3-3 3 3 0 0 1 3 3Zm11-2a3 3 0 1 1-3-3 3 3 0 0 1 3 3Z" />,
  // game: a pad
  <path key="pad" d="M6 9h4M8 7v4M15 10h.01M18 8h.01M7 4h10a5 5 0 0 1 5 5v4a4 4 0 0 1-7 2.6L14 15h-4l-1 .6A4 4 0 0 1 2 13V9a5 5 0 0 1 5-5Z" />,
];
const FAVS = ["Breaking Bad", "Bad Bunny", "The Legend of Zelda"];

function Bar({ value, tone }: { value: number; tone: keyof typeof TONE }) {
  return (
    <div className="relative mt-2 h-2 rounded-full bg-line">
      <div className={`grow h-full rounded-full ${TONE[tone].bar}`}
        style={{ width: `${value * 100}%`, animationDelay: "250ms" }} />
      {/* the 95% line a title must reach to be "watch now" */}
      <span className="absolute -top-1 h-4 w-0.5 rounded bg-ink/60" style={{ left: "95%" }} />
    </div>
  );
}

export default function HeroPreview({ onTry }: { onTry: () => void }) {
  const { t, f } = useI18n();
  const p = t.preview;
  const [step, setStep] = useState(2);
  const [still, setStill] = useState(true); // until mounted, and with reduced motion: last step, no timer
  const [paused, setPaused] = useState(false);
  const [run, setRun] = useState(0); // restarts the progress bar after a jump or a pause

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    setStill(false);
    setStep(0);
  }, []);
  useEffect(() => {
    if (still || paused) return;
    const id = setTimeout(() => setStep((s) => (s + 1) % 3), STEP_MS);
    return () => clearTimeout(id);
  }, [step, still, paused, run]);

  const jump = (i: number) => { setStep(i); setRun((r) => r + 1); };
  const resume = () => { setPaused(false); setRun((r) => r + 1); };

  return (
    <div className="relative">
      {/* soft glow behind the card */}
      <div aria-hidden className="pointer-events-none absolute -inset-y-6 inset-x-0 -z-10 rounded-[3rem] sm:-inset-x-6 bg-[radial-gradient(closest-side,color-mix(in_oklab,var(--accent)_22%,transparent),transparent)] blur-2xl" />
      <div role="region" aria-label={p.aria}
        onMouseEnter={() => setPaused(true)} onMouseLeave={resume}
        className="overflow-hidden rounded-[1.75rem] border border-line bg-card shadow-xl shadow-black/5">
        <div className="flex items-center justify-between gap-3 px-5 pt-4 text-xs uppercase tracking-wider text-muted">
          <span className="flex items-center gap-2">
            <span className="relative flex h-2 w-2" aria-hidden>
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60 motion-reduce:hidden" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
            </span>
            {p.label}
          </span>
        </div>

        <div className="mt-3 grid grid-cols-3 gap-2 px-5">
          {p.tabs.map((label, i) => (
            <button key={label} type="button" aria-pressed={step === i} onClick={() => jump(i)}
              className={`text-left text-xs font-medium transition-colors ${step === i ? "text-ink" : "text-muted hover:text-ink"}`}>
              <span className="tabular-nums">{i + 1}</span> · {label}
              <span className="mt-1.5 block h-1 overflow-hidden rounded-full bg-line">
                {i < step && <span className="block h-full w-full rounded-full bg-accent" />}
                {i === step && (
                  <span key={`${step}-${run}`} className={`${still ? "" : "fill"} block h-full rounded-full bg-accent`}
                    style={{ "--step-ms": `${STEP_MS}ms`, animationPlayState: paused ? "paused" : "running", width: still ? "100%" : undefined } as CSSProperties} />
                )}
              </span>
            </button>
          ))}
        </div>

        {/* fixed height so the page does not jump between steps */}
        <div className="relative h-[33rem] overflow-hidden px-5 pb-2 pt-5 sm:h-[30rem] lg:h-[32rem] lg:px-6">
          {step === 0 && (
            <div key="s0" className="rise">
              <p className="font-display text-2xl">{p.s1}</p>
              <ul className="mt-4 space-y-2.5">
                {FAVS.map((name, i) => (
                  <li key={name} className="rise flex items-center gap-3 rounded-2xl border border-line bg-paper p-2.5"
                    style={{ animationDelay: `${250 + i * 380}ms` }}>
                    <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-ink text-paper">
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                        {ICONS[i]}
                      </svg>
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{name}</span>
                      <span className="block text-xs text-muted">{p.kinds[i]}</span>
                    </span>
                    <span className="appear grid h-6 w-6 shrink-0 place-items-center rounded-full bg-good-soft text-xs text-good"
                      style={{ animationDelay: `${500 + i * 380}ms` }} aria-hidden>✓</span>
                  </li>
                ))}
              </ul>
              <p className="rise mt-4 flex items-center gap-2 text-sm font-medium text-accent" style={{ animationDelay: "1600ms" }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                  <circle cx="5" cy="12" r="2" /><circle cx="19" cy="5" r="2" /><circle cx="19" cy="19" r="2" /><path d="M7 11l10-5M7 13l10 5" />
                </svg>
                {p.s1to}
              </p>
              <p className="rise mt-1.5 text-sm text-muted" style={{ animationDelay: "1900ms" }}>{p.s1sub}</p>
            </div>
          )}

          {step === 1 && (
            <div key="s1" className="rise">
              <p className="font-display text-2xl">{p.s2}</p>
              <ol className="mt-4 space-y-2.5 text-sm">
                {p.s2steps.map(([source, text], i) => (
                  <li key={source} className="rise flex items-center gap-3 rounded-2xl border border-line bg-paper p-3"
                    style={{ animationDelay: `${150 + i * 750}ms` }}>
                    <span className="relative grid h-6 w-6 shrink-0 place-items-center" aria-hidden>
                      <span className="gone absolute" style={{ animationDelay: `${750 + i * 750}ms` }}>
                        <span className="block h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
                      </span>
                      <span className="appear grid h-6 w-6 place-items-center rounded-full bg-good-soft text-xs text-good"
                        style={{ animationDelay: `${750 + i * 750}ms` }}>✓</span>
                    </span>
                    <span className="flex-1 leading-snug">{text}</span>
                    <span className="shrink-0 rounded-full bg-card px-2 py-0.5 text-xs text-muted ring-1 ring-line">{source}</span>
                  </li>
                ))}
              </ol>
              <div className="rise mt-5" style={{ animationDelay: "300ms" }}>
                <p className="text-xs text-muted">{p.s2bar(f.int(MEASURED), f.int(3000))}</p>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-line">
                  <div className="fill h-full rounded-full bg-accent" style={{ "--step-ms": "2600ms" } as CSSProperties} />
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div key="s2" className="rise">
              <p className="font-display text-2xl">{p.s3}</p>
              <ul className="mt-4 grid grid-cols-3 gap-2.5 text-sm sm:gap-3">
                {PICKS.map((c, i) => (
                  <li key={c.name} className="rise min-w-0" style={{ animationDelay: `${i * 400}ms` }}>
                    <div className="relative h-32 overflow-hidden rounded-xl bg-line sm:h-40">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={c.image} alt="" className={`h-full w-full object-cover ${c.tone === "later" ? "opacity-75 saturate-50" : ""}`} />
                      <span className={`absolute left-1.5 top-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums shadow-sm ${TONE[c.tone].badge}`}>
                        {f.pctFloor(c.coverage)}
                      </span>
                    </div>
                    <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-muted">{p.lists[i]}</p>
                    <p className="truncate font-display text-base leading-tight" lang="es" title={c.name}>{c.name}</p>
                    <p className="text-xs text-muted">{c.year}</p>
                    <Bar value={c.coverage} tone={c.tone} />
                  </li>
                ))}
              </ul>
              <p className="mt-1.5 text-right text-[11px] text-muted">{p.need}</p>
              <div className="rise mt-2 space-y-1.5 rounded-2xl border border-line bg-paper p-3 text-xs leading-snug" style={{ animationDelay: "1300ms" }}>
                <p><span className="font-semibold text-good">{p.why(PICKS[0].name)}</span> {p.reason}</p>
                <p><span className="font-semibold text-later" lang="es">{PICKS[2].name}:</span> {p.notYet(f.pctFloor(PICKS[2].coverage), f.int(LATER_TO_GO))}</p>
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-3">
          <p className="min-w-0 truncate text-xs text-muted">{FAVS.join(" · ")}</p>
          <button type="button" onClick={onTry}
            className="shrink-0 rounded-full bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-accent hover:text-accent-ink">
            {p.cta}
          </button>
        </div>
      </div>
    </div>
  );
}
