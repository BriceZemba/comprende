"use client";

import { useMemo, useState } from "react";
import { coverageAt, fitFor } from "@/lib/comprehension";
import { useI18n } from "@/lib/i18n";

export interface MapTitle {
  key: string;
  name: string;
  kind: "film" | "series";
  year: number | null;
  affinity: number;
  lift: number | null; // affinity for this learner minus the title's average across reference tastes
  because: string[];
  curve: number[];
}

type Zone = "watch" | "stretch" | "later";
const zoneOf = (c: number): Zone => {
  const f = fitFor(c);
  return f === "comfortable" || f === "watchable" ? "watch" : f === "stretch" ? "stretch" : "later";
};

// Plot geometry (SVG user units; the SVG scales to its container).
const W = 640, H = 380, L = 56, R = 16, T = 16, B = 52;
const Y_MIN = 0.85; // coverage below 85% sits on the floor line; most titles sit between 88% and 98%
const SLIDER_MIN = 500, SLIDER_MAX = 12000, SLIDER_STEP = 250;

function Marker({ zone }: { zone: Zone }) {
  // Shape differs by zone so colour is never the only cue.
  if (zone === "watch") return <circle r={6} className="fill-[var(--dot-watch)] stroke-card" strokeWidth={2} />;
  if (zone === "stretch") return <rect x={-6} y={-6} width={12} height={12} transform="rotate(45)" className="fill-[var(--dot-stretch)] stroke-card" strokeWidth={2} />;
  return <circle r={5} className="fill-card stroke-[var(--dot-later)]" strokeWidth={2.5} />;
}

export default function TasteMap({ titles, grid, vocab }: { titles: MapTitle[]; grid: number[]; vocab: number }) {
  const { t, f, lang } = useI18n();
  const ZONE_LABEL = t.map.zones as Record<Zone, string>;
  const pctFloor = f.pctFloor;
  const aff = (a: number) => a.toLocaleString(lang, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const [v, setV] = useState(vocab);
  const [focus, setFocus] = useState<string | null>(null);

  // Horizontal position: how much more the title fits this learner than a typical taste (lift);
  // raw affinity would put the same generally liked titles on the right for everyone.
  const tasteOf = (m: MapTitle) => m.lift ?? m.affinity;
  const [aMin, aMax] = useMemo(() => {
    const a = titles.map(tasteOf);
    const lo = Math.min(...a), hi = Math.max(...a);
    const pad = Math.max(0.01, (hi - lo) * 0.08);
    return [lo - pad, hi + pad];
  }, [titles]);

  const x = (a: number) => L + ((a - aMin) / (aMax - aMin || 1)) * (W - L - R);
  const y = (c: number) => T + (1 - (Math.max(c, Y_MIN) - Y_MIN) / (1 - Y_MIN)) * (H - T - B);

  const points = titles.map((m) => {
    const c = coverageAt(grid, m.curve, v);
    return { ...m, c, zone: zoneOf(c) };
  });
  const counts = { watch: 0, stretch: 0, later: 0 } as Record<Zone, number>;
  points.forEach((p) => counts[p.zone]++);
  // Direct labels for the three strongest taste matches, staggered so they do not collide, and
  // anchored leftwards near the right edge so they stay inside the plot.
  const topTaste = new Map([...points].sort((a, b) => tasteOf(b) - tasteOf(a)).slice(0, 3).map((p, i) => [p.key, i]));
  const focused = points.find((p) => p.key === focus);

  if (titles.length < 3) return null;

  return (
    <section className="rise mt-10" aria-labelledby="map-title">
      <h3 id="map-title" className="font-display text-2xl">{t.map.title}</h3>
      <p className="mt-1 max-w-2xl text-sm text-muted">{t.map.lead}</p>
      <ul className="mt-3 grid max-w-3xl gap-2 text-sm sm:grid-cols-3">
        {t.map.howTo.map(([icon, text]) => (
          <li key={icon} className="flex gap-2 rounded-xl bg-card px-3 py-2">
            <span aria-hidden className="font-display text-lg leading-5 text-accent">{icon}</span>
            <span>{text}</span>
          </li>
        ))}
      </ul>

      <div className="relative mt-4 rounded-3xl border border-line bg-card p-3 sm:p-5">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img"
          aria-label={t.map.aria(titles.length, f.int(v), counts.watch, counts.stretch, counts.later)}
          onMouseLeave={() => setFocus(null)}>
          {/* zones */}
          <rect x={L} y={y(1)} width={W - L - R} height={y(0.95) - y(1)} className="fill-good-soft" />
          <rect x={L} y={y(0.95)} width={W - L - R} height={y(0.9) - y(0.95)} className="fill-warn-soft" />
          <rect x={L} y={y(0.9)} width={W - L - R} height={y(Y_MIN) - y(0.9)} className="fill-later-soft" />
          {(["watch", "stretch", "later"] as Zone[]).map((z) => {
            const yy = z === "watch" ? y(1) + 14 : z === "stretch" ? y(0.95) + 14 : y(0.9) + 14;
            return <text key={z} x={W - R - 6} y={yy} textAnchor="end" className="fill-muted text-[11px] max-sm:text-[20px]">{ZONE_LABEL[z]}</text>;
          })}
          {/* y axis */}
          {[0.85, 0.9, 0.95, 1].map((c) => (
            <g key={c}>
              <line x1={L} x2={W - R} y1={y(c)} y2={y(c)} className="stroke-line" strokeWidth={c === 0.95 || c === 0.9 ? 1.2 : 0.6} />
              <text x={L - 8} y={y(c) + 4} textAnchor="end" className="fill-muted text-[11px] tabular-nums max-sm:text-[20px]">{c === Y_MIN ? `≤${f.pct0(c)}` : f.pct0(c)}</text>
            </g>
          ))}
          <text x={14} y={T + (H - T - B) / 2} transform={`rotate(-90 14 ${T + (H - T - B) / 2})`} textAnchor="middle" className="fill-muted text-[11px] max-sm:text-[18px]">{t.map.yAxis}</text>
          {/* x axis */}
          <line x1={L} x2={W - R} y1={H - B} y2={H - B} className="stroke-line" />
          <text x={L} y={H - B + 22} className="fill-muted text-[11px] max-sm:text-[18px]">{t.map.less}</text>
          <text x={W - R} y={H - B + 22} textAnchor="end" className="fill-muted text-[11px] max-sm:text-[18px]">{t.map.more}</text>
          <text x={L + (W - L - R) / 2} y={H - 12} textAnchor="middle" className="fill-muted text-[11px] max-sm:hidden">{t.map.xAxis}</text>
          {/* dots */}
          {points.map((p) => (
            <g key={p.key} className="cursor-pointer outline-none transition-transform duration-300 ease-out motion-reduce:transition-none"
              style={{ transform: `translate(${x(tasteOf(p))}px, ${y(p.c)}px)` }}
              aria-hidden
              onMouseEnter={() => setFocus(p.key)} onFocus={() => setFocus(p.key)} onClick={() => setFocus(p.key)}>
              <circle r={14} fill="transparent" />
              <Marker zone={p.zone} />
              {topTaste.has(p.key) && (() => {
                const i = topTaste.get(p.key) ?? 0;
                const right = x(tasteOf(p)) > L + (W - L - R) * 0.6;
                return (
                  <text x={right ? -10 : 10} y={[-12, 20, -26][i]} textAnchor={right ? "end" : "start"}
                    className="pointer-events-none fill-ink stroke-card text-[11px] font-medium [paint-order:stroke] [stroke-width:3px] max-sm:hidden">
                    {p.name}
                  </text>
                );
              })()}
            </g>
          ))}
        </svg>

        {focused && (
          <div className="pointer-events-none absolute left-1/2 top-3 w-[min(90%,20rem)] -translate-x-1/2 rounded-xl border border-line bg-paper/95 p-3 text-sm shadow-lg">
            <p className="font-medium">{focused.name}{focused.year ? <span className="text-muted"> · {focused.year}</span> : null}</p>
            <p>{t.map.tipKnow(pctFloor(focused.c), ZONE_LABEL[focused.zone])}</p>
            {focused.because.length > 0 && <p className="text-muted">{t.res.becauseYouLike} {focused.because.join(", ")}</p>}
            <p className="text-xs text-muted">{t.map.cols[3]} {aff(focused.affinity)}</p>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm" aria-label={t.map.legend}>
          {(["watch", "stretch", "later"] as Zone[]).map((z) => (
            <span key={z} className="flex items-center gap-2">
              <svg width="16" height="16" viewBox="-8 -8 16 16" aria-hidden><Marker zone={z} /></svg>
              {ZONE_LABEL[z]} <span className="tabular-nums text-muted">{counts[z]}</span>
            </span>
          ))}
        </div>

        <label className="mt-4 block text-sm">
          <span className="flex flex-wrap items-baseline justify-between gap-2">
            <span>{t.map.ifYouKnew(f.int(v))}</span>
            {v !== vocab && (
              <button type="button" onClick={() => setV(vocab)} className="text-muted underline">
                {t.map.back(f.int(vocab))}
              </button>
            )}
          </span>
          <input type="range" min={SLIDER_MIN} max={SLIDER_MAX} step={SLIDER_STEP} value={v}
            onChange={(e) => setV(Number(e.target.value))} className="mt-2 w-full accent-[var(--accent)]"
            aria-valuetext={t.map.sliderValue(f.int(v))} />
        </label>
      </div>

      {/* sr-only on the wrapper: a table ignores the 1px width and would widen the page */}
      <div className="sr-only">
      <table>
        <caption>{t.map.caption(f.int(v))}</caption>
        <thead><tr>{t.map.cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{points.map((p) => <tr key={p.key}><td>{p.name}</td><td>{pctFloor(p.c)}</td><td>{ZONE_LABEL[p.zone]}</td><td>{aff(p.affinity)}</td></tr>)}</tbody>
      </table>
      </div>
    </section>
  );
}
