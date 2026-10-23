// A static preview of a real result (live run on 2026-10-23: Breaking Bad + Bad Bunny + The Legend of
// Zelda at ~3,000 words), labelled as an example. Decorative dots echo the taste x comprehension map.
const DOTS: [number, number, "watch" | "stretch" | "later"][] = [
  [30, 22, "watch"], [52, 16, "watch"], [70, 26, "watch"], [84, 18, "watch"], [44, 34, "stretch"],
  [62, 40, "stretch"], [78, 46, "stretch"], [24, 52, "stretch"], [56, 66, "later"], [88, 70, "later"],
];
const FILL = { watch: "var(--dot-watch)", stretch: "var(--dot-stretch)", later: "var(--dot-later)" };

export default function HeroPreview() {
  return (
    <div className="relative rounded-3xl border border-line bg-card p-5 shadow-sm" aria-label="Example result">
      <p className="text-xs uppercase tracking-wider text-muted">Example · fan of Breaking Bad, Bad Bunny, Zelda · ~3,000 words</p>
      <svg viewBox="0 0 100 80" className="mt-3 h-28 w-full" aria-hidden>
        <rect x="0" y="0" width="100" height="30" className="fill-good-soft" />
        <rect x="0" y="30" width="100" height="25" className="fill-warn-soft" />
        <rect x="0" y="55" width="100" height="25" className="fill-later-soft" />
        {DOTS.map(([x, y, z], i) => (
          <circle key={i} cx={x} cy={y} r="2.6" style={{ fill: FILL[z] }} />
        ))}
      </svg>
      <ul className="mt-3 space-y-2 text-sm">
        <li className="flex items-center justify-between gap-3">
          <span><strong className="font-display text-base">Sin nombre</strong> <span className="text-muted">· film</span></span>
          <span className="rounded-full bg-good-soft px-2 py-0.5 text-xs font-medium text-good">Watch now · 97%</span>
        </li>
        <li className="flex items-center justify-between gap-3">
          <span><strong className="font-display text-base">Celda 211</strong> <span className="text-muted">· film</span></span>
          <span className="rounded-full bg-good-soft px-2 py-0.5 text-xs font-medium text-good">Watch now · 95%</span>
        </li>
        <li className="flex items-center justify-between gap-3">
          <span><strong className="font-display text-base">Balada triste de trompeta</strong></span>
          <span className="rounded-full bg-later-soft px-2 py-0.5 text-xs font-medium text-later">Held back · 89%</span>
        </li>
      </ul>
    </div>
  );
}
