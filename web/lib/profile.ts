// The learner's progress, kept on this device only (localStorage): favourites, level, saved titles and
// what they watched. It is what makes a second visit useful: as the level grows, titles that were too hard
// come within reach, and the app can say so. No account, nothing sent anywhere.
import type { Favourite } from "@/components/FavouritesStep";
import type { Pick, RunResult, Variety } from "./api";
import { coverageAt } from "./comprehension.ts";  // with the extension so node can run lib/profile.test.ts

export type Verdict = "easy" | "ok" | "hard";

export interface SavedTitle {
  key: string;
  name: string;
  kind: "film" | "series";
  year: number | null;
  image: string | null;
  vocab_for_95: number | null;
  savedAt: string;
  watched?: { verdict: Verdict; at: string };
}

export interface Profile {
  favourites: Favourite[];
  vocab: number;
  shownAtVocab: number; // the level the last picks were made for: titles unlocked since are counted from it
  variety?: Variety;
  list: SavedTitle[];
  heldBack: { name: string; vocab_for_95: number | null } | null;
  map: { grid: number[]; titles: { key: string; curve: number[] }[] } | null;
  lastVisit: string;
}

const KEY = "comprende:profile";
const MIN_VOCAB = 500, MAX_VOCAB = 12000;

export function loadProfile(): Profile | null {
  try {
    const p = JSON.parse(localStorage.getItem(KEY) ?? "null");
    return p && typeof p.vocab === "number" && Array.isArray(p.list) ? p : null;
  } catch {
    return null;
  }
}

export function saveProfile(p: Profile | null): void {
  try {
    if (p) localStorage.setItem(KEY, JSON.stringify(p));
    else localStorage.removeItem(KEY);
  } catch { /* storage blocked: the visit still works, it is just not remembered */ }
}

/** The profile after a run: same list, new favourites, level, map and held-back title. */
export function afterRun(prev: Profile | null, favourites: Favourite[], vocab: number, result: RunResult): Profile {
  return {
    favourites,
    vocab,
    variety: result.variety ?? "any",
    shownAtVocab: vocab,
    list: prev?.list ?? [],
    heldBack: result.held_back ? { name: result.held_back.name, vocab_for_95: result.held_back.vocab_for_95 } : null,
    map: result.map ? { grid: result.map.grid, titles: result.map.titles.map((t) => ({ key: t.key, curve: t.curve })) }
      : null,
    lastVisit: new Date().toISOString(),
  };
}

export const listKey = (p: Pick) => p.qloo_id ?? p.imdb ?? p.name;

export function toggleSaved(prof: Profile, p: Pick): Profile {
  const key = listKey(p);
  const list = prof.list.some((s) => s.key === key) ? prof.list.filter((s) => s.key !== key)
    : [{ key, name: p.name, kind: p.kind, year: p.year, image: p.image, vocab_for_95: p.vocab_for_95,
         savedAt: new Date().toISOString() }, ...prof.list];
  return { ...prof, list };
}

/**
 * A rough level update after a film, not a test: watching in Spanish teaches words, so finishing one
 * nudges the estimate up a little (+3%), an easy one more (+10%), and one that was too hard brings it
 * down (-15%), like the "Too hard" reaction on a card. Rounded to 50, kept within the word check's range.
 */
export function adjustVocab(vocab: number, verdict: Verdict): number {
  const factor = verdict === "easy" ? 1.1 : verdict === "ok" ? 1.03 : 0.85;
  const next = Math.round((vocab * factor) / 50) * 50;
  return Math.min(MAX_VOCAB, Math.max(MIN_VOCAB, next));
}

export function markWatched(prof: Profile, key: string, verdict: Verdict): Profile {
  return {
    ...prof,
    vocab: adjustVocab(prof.vocab, verdict),
    list: prof.list.map((s) => (s.key === key ? { ...s, watched: { verdict, at: new Date().toISOString() } } : s)),
  };
}

/** How many measured titles reach comfortable coverage (95%) at `to` but not at `from`. */
export function unlocked(prof: Profile, from: number, to: number): number {
  if (!prof.map || to <= from) return 0;
  const { grid, titles } = prof.map;
  return titles.filter((t) => coverageAt(grid, t.curve, to) >= 0.95 && coverageAt(grid, t.curve, from) < 0.95).length;
}
