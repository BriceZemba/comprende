import type { MapTitle } from "@/components/TasteMap";
import type { Band, VocabItem } from "./comprehension";

export interface SearchHit {
  id: string;
  name: string;
  kind: string;
  year: number | null;
  image: string | null;
}

export interface Pick {
  qloo_id: string | null;
  imdb: string | null;
  name: string;
  name_en: string | null;
  kind: "film" | "series";
  year: number | null;
  image: string | null;
  description: string | null;
  affinity: number | null;
  lift: number | null;
  popularity: number | null;
  because: string[];
  coverage: number | null;
  fit: "comfortable" | "watchable" | "stretch" | "later" | null;
  vocab_for_95: number | null;
  words_to_go: number | null;
  bucket: "watch_now" | "stretch" | "later" | "unmeasured";
}

export interface ListenPick {
  qloo_id: string;
  name: string;
  kind: "artist" | "podcast";
  image: string | null;
  description: string | null;
  affinity: number | null;
  because: string[];
  spanish_tags: string[];
}

export interface RunResult {
  mode: "agent" | "fallback";
  model: string | null;
  vocab_size: number;
  favourites: Record<string, string>;
  qloo_calls: number;
  qloo_errors?: string[];
  qloo_unavailable?: boolean;
  buckets: Record<Pick["bucket"], Pick[]>;
  held_back: Pick | null;
  counts: Record<Pick["bucket"], number>;
  measured_share: number;
  map: { grid: number[]; titles: MapTitle[] };
  listen?: { artists: ListenPick[]; podcasts: ListenPick[] };
  // From the explainer agent, a moment after the result: one reason per pick, keyed like pickKey().
  explanations?: Record<string, Reason>;
}

export type Reason = { en: string; fr: string; es: string };

export type AgentEvent =
  // `text` is the English fallback; `data` lets the client say the same thing in the learner's language.
  | { type: "step"; tool: string; text: string; data?: Record<string, string | number | boolean> }
  | { type: "warning"; text: string; code?: string; data?: Record<string, string | number | boolean> }
  | { type: "message"; text: string }
  | { type: "error"; code: string; text: string }
  | { type: "result"; result: RunResult }
  | { type: "explanations"; explanations: Record<string, Reason> };

export interface VocabItemsFile {
  language: string;
  bands: Band[];
  items: VocabItem[];
  method: string;
}

export async function searchEntities(q: string, signal?: AbortSignal): Promise<SearchHit[]> {
  const r = await fetch(`/api/search?q=${encodeURIComponent(q)}`, { signal });
  if (!r.ok) throw new Error(`search ${r.status}`);
  return (await r.json()).results;
}

export async function getVocabItems(): Promise<VocabItemsFile> {
  const r = await fetch("/api/vocab/items");
  if (!r.ok) throw new Error(`vocab ${r.status}`);
  return r.json();
}

// Carries the HTTP status so the page can explain the failure in the learner's language.
export class AgentStartError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

export async function runAgent(
  body: {
    favourites_text: string;
    favourite_ids: Record<string, string>;
    vocab_size: number;
    exclude_ids?: string[];
  },
  onEvent: (e: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok || !r.body) {
    const detail = await r.json().catch(() => ({}));
    throw new AgentStartError(typeof detail.detail === "string" ? detail.detail : `The agent could not start (${r.status})`, r.status);
  }
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      if (chunk.startsWith("data: ")) onEvent(JSON.parse(chunk.slice(6)));
    }
  }
}
