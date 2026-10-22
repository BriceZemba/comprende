import { ImageResponse } from "next/og";

export const alt = "Comprende: Spanish you'll love, at a level you'll understand";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Social preview, drawn from the same palette as the site.
export default function OpengraphImage() {
  const dots = [
    [760, 170, "#0b8068"], [840, 150, "#0b8068"], [930, 185, "#0b8068"], [1010, 160, "#0b8068"],
    [800, 260, "#b4720f"], [890, 240, "#b4720f"], [980, 275, "#b4720f"],
    [770, 360, "#b0306f"], [950, 390, "#b0306f"],
  ] as const;
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", background: "#15120f", color: "#f3ece3", padding: 72, position: "relative" }}>
        <div style={{ display: "flex", flexDirection: "column", width: 640 }}>
          <div style={{ fontSize: 34, color: "#e0674b" }}>comprende</div>
          <div style={{ fontSize: 66, lineHeight: 1.08, marginTop: 36 }}>Spanish you&apos;ll love, at a level you&apos;ll understand.</div>
          <div style={{ fontSize: 26, color: "#a89c90", marginTop: 32 }}>
            Taste from the Qloo taste graph. Difficulty measured from real subtitles.
          </div>
        </div>
        <div style={{ position: "absolute", left: 720, top: 120, width: 400, height: 320, display: "flex", border: "2px solid #342c25", borderRadius: 24 }} />
        {dots.map(([x, y, c], i) => (
          <div key={i} style={{ position: "absolute", left: x, top: y, width: 26, height: 26, borderRadius: 13, background: c }} />
        ))}
        <div style={{ position: "absolute", left: 740, top: 470, fontSize: 22, color: "#a89c90" }}>taste match →</div>
      </div>
    ),
    size,
  );
}
