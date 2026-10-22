import type { NextConfig } from "next";

// The browser talks to /api on this origin; Next proxies to the FastAPI backend,
// so the Qloo key and the backend URL never reach the client.
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  images: { remotePatterns: [{ protocol: "https", hostname: "images.qloo.com" }] },
};

export default nextConfig;
