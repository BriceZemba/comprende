import type { MetadataRoute } from "next";

// Lets a learner add Comprende to their phone's home screen: an icon there is the simplest reason to
// come back to "My list" (kept on the device).
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Comprende: Spanish you'll love and understand",
    short_name: "Comprende",
    description: "Spanish films and series that match your taste and your level.",
    start_url: "/",
    display: "standalone",
    background_color: "#fbf7f1",
    theme_color: "#fbf7f1",
    icons: [
      { src: "/icons/192", sizes: "192x192", type: "image/png" },
      { src: "/icons/512", sizes: "512x512", type: "image/png" },
      { src: "/icons/512", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
