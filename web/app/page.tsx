"use client";

import { useEffect, useRef, useState } from "react";
import AgentRun from "@/components/AgentRun";
import HeroPreview from "@/components/HeroPreview";
import FavouritesStep, { type Favourite } from "@/components/FavouritesStep";
import LevelStep from "@/components/LevelStep";
import Results, { pickKey, type Feedback } from "@/components/Results";
import Header from "@/components/Header";
import { AgentStartError, runAgent, type AgentEvent, type RunResult } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type Stage = "intro" | "favourites" | "level" | "run" | "results";
interface Proof { titles: number; ours: number; llm: number; personal: number; noQloo: number }
const EXAMPLE: Favourite[] = [
  { id: null, name: "Breaking Bad" }, { id: null, name: "Bad Bunny" }, { id: null, name: "The Legend of Zelda" },
];

export default function Home() {
  const { t, f } = useI18n();
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
      setError(e instanceof AgentStartError && e.status === 429 ? t.run.tooMany
        : e instanceof AgentStartError && e.status >= 500 ? t.run.unreachable
        : e instanceof Error && e.name !== "TypeError" ? e.message : t.run.unreachable);
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
    if (loved.length) parts.push(t.res.added(loved.map((p) => p.name).join(", ")));
    if (hard.length) parts.push(t.res.lowered(f.int(vocab), f.int(v), hard.map((p) => p.name).join(", ")));
    setNote(parts.length ? t.res.updated(parts) : null);
    setFavourites(favs); setExcluded(exclude);
    start(v, favs, exclude);
  };

  return (
    <main className="mx-auto max-w-5xl px-4 pb-24 sm:px-8">
      {fake && (
        <p className="mt-3 rounded-xl bg-accent px-4 py-2 text-center text-sm font-medium text-accent-ink">
          {t.devBanner}
        </p>
      )}
      <Header onLogo={() => go("intro")} nav={<>
        <a href="#how" className="hover:text-ink">{t.nav.how}</a>
        <a href="/method" className="hover:text-ink">{t.nav.method}</a>
      </>} />
      <div ref={top} className="scroll-mt-4" />

      {stage === "intro" && (
        <section className="rise pt-4 sm:pt-10">
          <div className="grid items-center gap-10 lg:grid-cols-[1.25fr_1fr]">
            <div>
              <h1 className="font-display text-5xl leading-[1.05] sm:text-6xl lg:text-7xl">
                {t.intro.title((s) => <em className="text-accent">{s}</em>, (s) => <em className="text-accent">{s}</em>)}
              </h1>
              <p className="mt-6 max-w-2xl text-lg text-muted">
                {t.intro.lead}
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <button type="button" onClick={() => go("favourites")}
                  className="rounded-full bg-accent px-7 py-4 text-lg font-medium text-accent-ink shadow-sm hover:brightness-110">
                  {t.intro.start}
                </button>
                <button type="button" onClick={() => { setFavourites(EXAMPLE); setExcluded([]); setNote(null); start(3000, EXAMPLE, []); }}
                  className="rounded-full border border-line bg-card px-6 py-4 text-lg hover:border-accent">
                  {t.intro.example}
                </button>
              </div>
              <p className="mt-3 text-sm text-muted">{t.intro.sub}</p>
            </div>
            <HeroPreview />
          </div>
          {proof && (
            <dl className="mt-14 grid gap-4 border-t border-line pt-8 sm:grid-cols-3">
              <div>
                <dt className="text-sm text-muted">{t.intro.proofTitles}</dt>
                <dd className="font-display text-4xl">{f.int(proof.titles)}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted">{t.intro.proofFirst(f.pct1(proof.llm))}</dt>
                <dd className="font-display text-4xl">{f.pct1(proof.ours)}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted">{t.intro.proofPersonal(f.pct1(proof.noQloo))}</dt>
                <dd className="font-display text-4xl">{f.pct1(proof.personal)}</dd>
              </div>
              <p className="text-xs text-muted sm:col-span-3">
                {t.intro.proofFoot} <a href="/method" className="underline">{t.intro.proofLink}</a>.
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
              <button type="button" onClick={() => go("level")} className="mt-3 underline">{t.run.tryAgain}</button>
            </div>
          )}
        </>
      )}
      {stage === "results" && result && (
        <>
          <details className="mb-8 max-w-xl text-sm text-muted">
            <summary className="cursor-pointer">{t.run.steps(events.filter((e) => e.type === "step").length)}</summary>
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
        <h2 className="font-display text-3xl">{t.how.title}</h2>
        <div className="mt-6 grid gap-6 sm:grid-cols-3">
          {([[t.how.c1t, t.how.c1], [t.how.c2t, t.how.c2], [t.how.c3t, t.how.c3]] as const).map(([title, body]) => (
            <div key={title}>
              <p className="font-display text-xl">{title}</p>
              <p className="mt-2 text-muted">{body}</p>
            </div>
          ))}
        </div>
        <p className="mt-8 text-sm text-muted">
          {t.how.credits(<a className="underline" href="https://www.opensubtitles.org/">opensubtitles.org</a>)}
        </p>
      </section>

      <footer className="mt-16 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6 text-sm text-muted">
        <p>{t.footer.built}</p>
        <nav className="flex gap-5">
          <a href="/method" className="hover:text-ink">{t.nav.method}</a>
          <a href="https://github.com/BriceZemba/comprende" className="hover:text-ink">{t.footer.source}</a>
        </nav>
      </footer>
    </main>
  );
}
