"use client";

import { useEffect, useRef, useState } from "react";
import AgentRun from "@/components/AgentRun";
import HeroPreview from "@/components/HeroPreview";
import FavouritesStep, { type Favourite } from "@/components/FavouritesStep";
import LevelStep from "@/components/LevelStep";
import Results, { pickKey, type Feedback } from "@/components/Results";
import { runAgent, type AgentEvent, type RunResult } from "@/lib/api";

type Stage = "intro" | "favourites" | "level" | "run" | "results";
interface Proof { titles: number; ours: number; llm: number; personal: number; noQloo: number }
const pct1 = (x: number) => `${(x * 100).toFixed(1)}%`;
const EXAMPLE: Favourite[] = [
  { id: null, name: "Breaking Bad" }, { id: null, name: "Bad Bunny" }, { id: null, name: "The Legend of Zelda" },
];

export default function Home() {
  const [stage, setStage] = useState<Stage>("intro");
  const [favourites, setFavourites] = useState<Favourite[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const top = useRef<HTMLDivElement>(null);
  const [fake, setFake] = useState(false);
  const [proof, setProof] = useState<Proof | null>(null);
  useEffect(() => {
    fetch("/api/health").then((r) => r.json()).then((h) => setFake(!!h.fake_qloo)).catch(() => {});
    fetch("/api/method").then((r) => r.json()).then((m) => {
      const e = m.evaluation ?? {};
      if (m.validation && e.comprende && e.llm_only && e.no_qloo) {
        setProof({ titles: m.validation.titles, ours: e.comprende.first5_below_90, llm: e.llm_only.first5_below_90,
          personal: e.comprende.distinct_share, noQloo: e.no_qloo.distinct_share });
      }
    }).catch(() => {});
  }, []);

  const go = (s: Stage) => { setStage(s); top.current?.scrollIntoView({ behavior: "smooth" }); };

  const [vocab, setVocab] = useState(0);
  const [feedback, setFeedback] = useState<Record<string, Feedback>>({});
  const [excluded, setExcluded] = useState<string[]>([]);
  const [note, setNote] = useState<string | null>(null);

  const start = async (v: number, favs: Favourite[] = favourites, exclude: string[] = excluded) => {
    go("run");
    setVocab(v);
    setEvents([]); setResult(null); setError(null); setFeedback({});
    try {
      await runAgent(
        {
          favourites_text: favs.filter((f) => !f.id).map((f) => f.name).join(", "),
          favourite_ids: Object.fromEntries(favs.filter((f) => f.id).map((f) => [f.id as string, f.name])),
          vocab_size: v,
          exclude_ids: exclude,
        },
        (e) => {
          setEvents((prev) => [...prev, e]);
          if (e.type === "result") { setResult(e.result); setStage("results"); }
          if (e.type === "error") setError(e.text);
        },
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "The agent could not start.");
    }
  };

  // Learner reactions become the next plan: loved titles become taste signals, every reacted title is
  // excluded from the next list, and "too hard" lowers the vocabulary estimate by a fifth.
  const update = () => {
    if (!result) return;
    const all = Object.values(result.buckets).flat();
    const byKey = Object.fromEntries(all.map((p) => [pickKey(p), p]));
    const loved = Object.entries(feedback).filter(([, f]) => f === "loved").map(([k]) => byKey[k]).filter(Boolean);
    const hard = Object.entries(feedback).filter(([, f]) => f === "too_hard").map(([k]) => byKey[k]).filter(Boolean);
    const favs = [...favourites, ...loved.filter((p) => p.qloo_id && !favourites.some((f) => f.id === p.qloo_id))
      .map((p) => ({ id: p.qloo_id, name: p.name, kind: p.kind === "series" ? "tv_show" : "movie" }))];
    const exclude = [...new Set([...excluded, ...Object.keys(feedback)])];
    const v = hard.length ? Math.round((vocab * 0.8) / 50) * 50 : vocab;
    const parts = [];
    if (loved.length) parts.push(`added ${loved.map((p) => p.name).join(", ")} to your taste`);
    if (hard.length) parts.push(`lowered your level from about ${vocab.toLocaleString()} to ${v.toLocaleString()} words because ${hard.map((p) => p.name).join(", ")} felt too hard`);
    setNote(parts.length ? `Updated: ${parts.join("; ")}.` : null);
    setFavourites(favs); setExcluded(exclude);
    start(v, favs, exclude);
  };

  return (
    <main className="mx-auto max-w-5xl px-4 pb-24 sm:px-8">
      {fake && (
        <p className="mt-3 rounded-xl bg-accent px-4 py-2 text-center text-sm font-medium text-accent-ink">
          Development mode: taste scores are fake placeholders, not Qloo data.
        </p>
      )}
      <header className="flex items-center justify-between py-6">
        <button type="button" onClick={() => go("intro")} className="font-display text-2xl">comprende</button>
        <nav className="flex gap-5 whitespace-nowrap text-sm text-muted">
          <a href="#how" className="hidden hover:text-ink sm:inline">How it works</a>
          <a href="/method" className="hover:text-ink">
            Method<span className="hidden sm:inline"> &amp; evidence</span>
          </a>
        </nav>
      </header>
      <div ref={top} className="scroll-mt-4" />

      {stage === "intro" && (
        <section className="rise pt-4 sm:pt-10">
          <div className="grid items-center gap-10 lg:grid-cols-[1.25fr_1fr]">
            <div>
              <h1 className="font-display text-5xl leading-[1.05] sm:text-6xl lg:text-7xl">
                Spanish you&apos;ll <em className="text-accent">love</em>, at a level you&apos;ll <em className="text-accent">understand</em>.
              </h1>
              <p className="mt-6 max-w-2xl text-lg text-muted">
                Learners quit native shows when they are boring or impossible to follow. Comprende starts from what you
                already love, uses the Qloo taste graph to find Spanish films and series with the same feel, and checks
                each one&apos;s dialogue against the words you know.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <button type="button" onClick={() => go("favourites")}
                  className="rounded-full bg-accent px-7 py-4 text-lg font-medium text-accent-ink shadow-sm hover:brightness-110">
                  Find my first Spanish show →
                </button>
                <button type="button" onClick={() => { setFavourites(EXAMPLE); setExcluded([]); setNote(null); start(3000, EXAMPLE, []); }}
                  className="rounded-full border border-line bg-card px-6 py-4 text-lg hover:border-accent">
                  Try an example
                </button>
              </div>
              <p className="mt-3 text-sm text-muted">Two minutes. No sign-up. The example runs for a fan of Breaking Bad, Bad Bunny and Zelda.</p>
            </div>
            <HeroPreview />
          </div>
          {proof && (
            <dl className="mt-14 grid gap-4 border-t border-line pt-8 sm:grid-cols-3">
              <div>
                <dt className="text-sm text-muted">Spanish films and series measured from real subtitles</dt>
                <dd className="font-display text-4xl">{proof.titles.toLocaleString()}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted">First picks the learner could barely follow (a chatbot alone: {pct1(proof.llm)})</dt>
                <dd className="font-display text-4xl">{pct1(proof.ours)}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted">Different titles across 20 learners (without Qloo: {pct1(proof.noQloo)})</dt>
                <dd className="font-display text-4xl">{pct1(proof.personal)}</dd>
              </div>
              <p className="text-xs text-muted sm:col-span-3">
                From our evaluation on 20 fixed taste profiles. <a href="/method" className="underline">How we measured it</a>.
              </p>
            </dl>
          )}
        </section>
      )}

      {stage === "favourites" && <FavouritesStep value={favourites} onChange={setFavourites} onNext={() => go("level")} />}
      {stage === "level" && <LevelStep onBack={() => go("favourites")} onDone={(v) => { setNote(null); start(v); }} />}
      {stage === "run" && (
        <>
          <AgentRun events={events} running={!error} />
          {error && (
            <div className="mt-6 max-w-xl rounded-2xl bg-warn-soft p-5">
              <p>{error}</p>
              <button type="button" onClick={() => go("level")} className="mt-3 underline">Try again</button>
            </div>
          )}
        </>
      )}
      {stage === "results" && result && (
        <>
          <details className="mb-8 max-w-xl text-sm text-muted">
            <summary className="cursor-pointer">What the agent did ({events.filter((e) => e.type === "step").length} steps)</summary>
            <AgentRun events={events} running={false} />
          </details>
          <Results
            result={result}
            feedback={feedback}
            onFeedback={(p, f) => setFeedback((prev) => {
              const next = { ...prev };
              if (f) next[pickKey(p)] = f; else delete next[pickKey(p)];
              return next;
            })}
            onUpdate={update}
            onChangeLevel={(v) => { setNote(null); start(v); }}
            note={note}
            onRestart={() => { setFavourites([]); setExcluded([]); setNote(null); go("favourites"); }}
          />
        </>
      )}

      <section id="how" className="mt-28 border-t border-line pt-12">
        <h2 className="font-display text-3xl">How it works</h2>
        <div className="mt-6 grid gap-6 sm:grid-cols-3">
          <div>
            <p className="font-display text-xl">1 · Taste, from Qloo</p>
            <p className="mt-2 text-muted">
              Your favourites, from any domain, become signals in Qloo&apos;s taste graph. Qloo returns films and series
              released in Spanish-speaking countries that people with your taste love, and says which favourite drove
              each match.
            </p>
          </div>
          <div>
            <p className="font-display text-xl">2 · Difficulty, from real subtitles</p>
            <p className="mt-2 text-muted">
              For each Spanish-original title we have subtitles for, we measured the share of words a learner with a
              given vocabulary would know. Research on listening and reading puts comfortable comprehension near 95–98%.
            </p>
          </div>
          <div>
            <p className="font-display text-xl">3 · An agent that holds back</p>
            <p className="mt-2 text-muted">
              The agent ranks by both, and keeps the title you&apos;d love most but can&apos;t follow yet for later,
              instead of setting you up to quit.
            </p>
          </div>
        </div>
        <p className="mt-8 text-sm text-muted">
          Taste data: Qloo. Titles: Wikidata. Subtitles: OPUS OpenSubtitles corpus (Lison &amp; Tiedemann 2016), from{" "}
          <a className="underline" href="https://www.opensubtitles.org/">opensubtitles.org</a>. Only word counts are kept.
        </p>
      </section>

      <footer className="mt-16 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6 text-sm text-muted">
        <p>Comprende · built for the Qloo Agentic Hackathon 2026</p>
        <nav className="flex gap-5">
          <a href="/method" className="hover:text-ink">Method &amp; evidence</a>
          <a href="https://github.com/BriceZemba/comprende" className="hover:text-ink">Source code</a>
        </nav>
      </footer>
    </main>
  );
}
