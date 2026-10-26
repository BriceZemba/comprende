import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

// Home-screen icon on iPhone, same as the app icon.
export default function AppleIcon() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
        background: "#c2462b", color: "#fbf7f1", fontSize: 112, fontWeight: 700, paddingBottom: 14 }}>
        c
      </div>
    ),
    size,
  );
}
