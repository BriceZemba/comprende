import { ImageResponse } from "next/og";

// App icon for the home screen, drawn from the site palette: a terracotta square with a "c".
export async function GET(_req: Request, { params }: { params: Promise<{ size: string }> }) {
  const size = Math.min(1024, Math.max(48, Number((await params).size) || 192));
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
        background: "#c2462b", color: "#fbf7f1", fontSize: size * 0.62, fontWeight: 700, paddingBottom: size * 0.08 }}>
        c
      </div>
    ),
    { width: size, height: size, headers: { "Cache-Control": "public, max-age=86400, immutable" } },
  );
}
