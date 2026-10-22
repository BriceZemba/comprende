// Streams the agent's server-sent events from the backend to the browser.
// A plain rewrite buffers the whole response, so the live step list would only appear at the end.
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

export async function POST(req: Request) {
  const forwardedFor = req.headers.get("x-forwarded-for") ?? "";
  const upstream = await fetch(`${backend}/api/recommend`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Forwarded-For": forwardedFor,
      "X-Comprende-Proxy": process.env.PROXY_SECRET ?? "",
    },
    body: await req.text(),
  });
  if (!upstream.ok || !upstream.body) {
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
    });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
