"use client";

import { useEffect, useRef, useState } from "react";
import AgentRun from "@/components/AgentRun";
import CanIFollow from "@/components/CanIFollow";
import WeeklyReminder from "@/components/WeeklyReminder";
import HeroPreview from "@/components/HeroPreview";
import FavouritesStep, { type Favourite } from "@/components/FavouritesStep";
import LevelStep from "@/components/LevelStep";
import Results, { pickKey, type Feedback } from "@/components/Results";
import Header from "@/components/Header";
import MyList from "@/components/MyList";
import WelcomeBack from "@/components/WelcomeBack";
import { AgentStartError, runAgent, type AgentEvent, type RunResult, type Variety } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { afterRun, listKey, loadProfile, saveProfile, toggleSaved, type Profile } from "@/lib/profile";

type Stage = "intro" | "favourites" | "level" | "run" | "results";
interface Proof { titles: number; ours: number; llm: number; personal: number; noQloo: number }
const SAVED = "comprende:last"; // sessionStorage: the last results survive a reload or Back
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
  const [watchOn, setWatchOn] = useState(false);
  const [proof, setProof] = useState<Proof | null>(null);
  useEffect(() => {
    fetch("/api/health").then((r) => r.json()).then((h) => { setFake(!!h.fake_qloo); setWatchOn(!!h.watch_providers); })
      .catch(() => {});
    fetch("/api/method").then((r) => r.json()).then((m) => {
      const e = m.evaluation ?? {};
      if (m.validation && e.comprende && e.llm_only && e.no_qloo) {
        setProof({ titles: m.validation.titles, ours: e.comprende.first5_below_90, llm: e.llm_only.first5_below_90,
          personal: e.comprende.distinct_share, noQloo: e.no_qloo.distinct_share });
      }
    }).catch(() => {});
  }, []);

  // Each step is a browser history entry, so Back on a phone returns to the previous step instead of
  // leaving the app. The run itself is replaced by its results, so Back from results goes to the level.
  const go = (s: Stage, how: "push" | "replace" | "none" = "push") => {
    setStage(s);
    try {
      if (how === "push") history.pushState({ stage: s }, "");
      if (how === "replace") history.replaceState({ stage: s }, "");
    } catch { /* history unavailable: steps still work */ }
  };
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    // New step: start at its top and move keyboard and screen-reader focus to its heading.
    const el = top.current;
    if (el && el.getBoundingClientRect().top < 0) el.scrollIntoView({ block: "start" });
    const h = document.querySelector<HTMLElement>("main section h1, main section h2");
    if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); }
  }, [stage]);

  const [vocab, setVocab] = useState(0);
  const [feedback, setFeedback] = useState<Record<string, Feedback>>({});
  const [excluded, setExcluded] = useState<string[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [variety, setVariety] = useState<Variety>("any");
  // Progress kept on this device (lib/profile.ts): read after mount, since the server cannot see it.
  const [profile, setProfileState] = useState<Profile | null>(null);
  useEffect(() => { setProfileState(loadProfile()); }, []);
  const setProfile = (p: Profile | null) => { setProfileState(p); saveProfile(p); };
  // Changes built from the latest profile, so two quick clicks both count.
  const updateProfile = (change: (p: Profile) => Profile) => setProfileState((prev) => {
    if (!prev) return prev;
    const next = change(prev);
    saveProfile(next);
    return next;
  });

  useEffect(() => {
    const onPop = (e: PopStateEvent) => {
      const s = (e.state?.stage as Stage | undefined) ?? "intro";
      // A run cannot be resumed from history; its entry leads back to the level step.
      setStage(s === "run" ? "level" : s === "results" && !result ? "intro" : s);
    };
    addEventListener("popstate", onPop);
    return () => removeEventListener("popstate", onPop);
  }, [result]);

  // A shared link (?f=Breaking Bad|Bad Bunny&v=3000) proposes the same search; nothing runs until asked.
  const [shared, setShared] = useState<{ favs: Favourite[]; v: number; variety: Variety } | null>(null);
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    const names = (q.get("f") ?? "").split("|").map((x) => x.trim()).filter(Boolean).slice(0, 8);
    const v = Math.min(12000, Math.max(500, Number(q.get("v")) || 3000));
    const sv = (["spain", "latam"] as const).find((x) => x === q.get("s")) ?? "any";
    if (names.length) {
      setShared({ favs: names.map((name) => ({ id: null, name })), v, variety: sv });
      history.replaceState(history.state, "", location.pathname);
    }
  }, []);
  const share = async (): Promise<boolean> => {
    const url = `${location.origin}/?f=${encodeURIComponent(favourites.map((x) => x.name).join("|"))}&v=${vocab}`
      + (variety !== "any" ? `&s=${variety}` : "");
    try {
      if (navigator.share) { await navigator.share({ title: "Comprende", text: t.res.shareText, url }); return false; }
      await navigator.clipboard.writeText(url);
      return true;
    } catch { return false; }
  };

  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(SAVED) ?? "null");
      const s = history.state?.stage as Stage | undefined;
      if (saved?.result && s === "results") {
        setResult(saved.result); setEvents(saved.events ?? []); setVocab(saved.vocab ?? 0);
        setFavourites(saved.favourites ?? []); setExcluded(saved.excluded ?? []); setStage("results");
      } else if (s === "favourites" || s === "level") {
        setFavourites(saved?.favourites ?? []); setStage(s);
      }
    } catch { /* nothing saved, or storage blocked */ }
  }, []);

  // One handler for live runs and for the recorded example's replay.
  const onEvent = (e: AgentEvent, favs: Favourite[], v: number, exclude: string[], collected: AgentEvent[]) => {
          setEvents((prev) => [...prev, e]);
          if (e.type === "result") {
            setResult(e.result); go("results", "replace");
            setProfile(afterRun(loadProfile(), favs, v, e.result));
            try {
              sessionStorage.setItem(SAVED, JSON.stringify({ result: e.result, events: [...collected, e], vocab: v,
                favourites: favs, excluded: exclude }));
            } catch { /* not saved: results still show */ }
          }
          if (e.type === "explanations") {
            // The explainer's reasons arrive after the cards: merge them into the shown result.
            setResult((prev) => {
              if (!prev) return prev;
              const next = { ...prev, explanations: e.explanations };
              try {
                const saved = JSON.parse(sessionStorage.getItem(SAVED) ?? "null");
                if (saved?.result) sessionStorage.setItem(SAVED, JSON.stringify({ ...saved, result: next }));
              } catch { /* not saved */ }
              return next;
            });
          }
          collected.push(e);
          if (e.type === "error") setError(e.text);
  };

  const [recordedAt, setRecordedAt] = useState<string | null>(null);
  const begin = (v: number) => {
    go("run");
    setVocab(v);
    setEvents([]); setResult(null); setError(null); setFeedback({});
  };

  const start = async (v: number, favs: Favourite[] = favourites, exclude: string[] = excluded, spanish: Variety = variety) => {
    begin(v);
    setRecordedAt(null);
    const collected: AgentEvent[] = [];
    try {
      await runAgent(
        {
          favourites_text: favs.filter((f) => !f.id).map((f) => f.name).join(", "),
          favourite_ids: Object.fromEntries(favs.filter((f) => f.id).map((f) => [f.id as string, f.name])),
          vocab_size: v,
          exclude_ids: exclude,
          variety: spanish,
        },
        (e) => onEvent(e, favs, v, exclude, collected),
      );
    } catch (e) {
      setError(e instanceof AgentStartError && e.status === 429 ? t.run.tooMany
        : e instanceof AgentStartError && e.status >= 500 ? t.run.unreachable
        : e instanceof Error && e.name !== "TypeError" ? e.message : t.run.unreachable);
    }
  };

  // The home-page example replays a recorded real run (backend/scripts/record_example.py), labelled with
  // its date: the most-clicked path then costs none of the hosted demo's free model quota. A learner's own
  // search always runs live; if no recording is available, the example runs live too.
  const playExample = async () => {
    setFavourites(EXAMPLE); setExcluded([]); setNote(null);
    let rec: { recorded_at: string; vocab: number; events: { event: AgentEvent }[] } | null = null;
    try {
      const r = await fetch("/api/example");
      if (r.ok) rec = await r.json();
    } catch { /* replay unavailable: run live */ }
    if (!rec) { start(3000, EXAMPLE, []); return; }
    begin(rec.vocab);
    setRecordedAt(rec.recorded_at);
    const collected: AgentEvent[] = [];
    for (const { event } of rec.events) {
      await new Promise((ok) => setTimeout(ok, event.type === "step" ? 320 : event.type === "explanations" ? 900 : 200));
      onEvent(event, EXAMPLE, rec.vocab, [], collected);
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
    <div className="mx-auto max-w-5xl px-4 pb-24 sm:px-8">
      {fake && (
        <p className="mt-3 rounded-xl bg-accent px-4 py-2 text-center text-sm font-medium text-accent-ink">
          {t.devBanner}
        </p>
      )}
      <Header onLogo={() => go("intro")} nav={<>
        <a href="#check" className="hover:text-ink" onClick={(e) => {
          if (stage === "intro") return; // the section is on this page: the link scrolls to it
          e.preventDefault();
          go("intro");
          setTimeout(() => document.getElementById("check")?.scrollIntoView({ block: "start" }), 60);
        }}>{t.nav.check}</a>
        <a href="#how" className="hover:text-ink">{t.nav.how}</a>
        <a href="/method" className="hover:text-ink">{t.nav.method}</a>
      </>} />
      <main>
      <div ref={top} className="scroll-mt-4" />

      {stage === "intro" && (
        <section className="rise pt-4 sm:pt-10">
          {shared && (
            <div className="mb-10 rounded-3xl border border-accent/40 bg-card p-5 sm:p-6">
              <p className="font-display text-2xl">{t.shared.title}</p>
              <p className="mt-2">{t.shared.body(shared.favs.map((x) => x.name).join(" · "), f.int(shared.v))}</p>
              <button type="button" onClick={() => { const s = shared; setShared(null); setFavourites(s.favs); setExcluded([]); setNote(null); setVariety(s.variety); start(s.v, s.favs, [], s.variety); }}
                className="mt-4 rounded-full bg-accent px-6 py-3 font-medium text-accent-ink shadow-sm hover:brightness-110">
                {t.shared.go}
              </button>
            </div>
          )}
          {/* a returning learner sees where they stand first */}
          {profile && (
            <div className="mb-10">
              <WelcomeBack profile={profile}
                onFresh={() => {
                  const seen = profile.list.filter((s) => s.watched).map((s) => s.key);
                  setFavourites(profile.favourites); setExcluded(seen); setNote(null);
                  setVariety(profile.variety ?? "any");
                  start(profile.vocab, profile.favourites, seen, profile.variety ?? "any");
                }}
                onForget={() => setProfile(null)} />
            </div>
          )}
          <div className="relative grid grid-cols-1 items-center gap-12 lg:grid-cols-[1fr_1.1fr] lg:gap-14">
            <div aria-hidden className="pointer-events-none absolute -left-40 -top-32 -z-10 h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(closest-side,color-mix(in_oklab,var(--good)_14%,transparent),transparent)] blur-2xl" />
            <div>
              <p className="mb-6 inline-flex items-center gap-2 rounded-full border border-line bg-card px-3.5 py-1.5 text-xs font-medium text-muted shadow-sm sm:text-sm">
                <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
                {t.intro.eyebrow(f.int(proof?.titles ?? 1464))}
              </p>
              <h1 className="font-display text-5xl leading-[1.04] tracking-tight sm:text-6xl lg:text-[4rem]">
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
                <button type="button" onClick={playExample}
                  className="rounded-full border border-line bg-card px-6 py-4 text-lg shadow-sm hover:border-accent">
                  {t.intro.example}
                </button>
              </div>
              <p className="mt-3 text-sm text-muted">{t.intro.sub}</p>
            </div>
            <HeroPreview onTry={playExample} />
          </div>
          {profile && (
            <>
              <MyList profile={profile} onChange={setProfile} />
              <WeeklyReminder profile={profile} />
            </>
          )}

          <CanIFollow vocab={profile?.vocab ?? 3000} onCheck={() => go("level")} />

          {proof && (
            <dl className="mt-16 grid gap-3 sm:grid-cols-3">
              {([
                [t.intro.proofTitles, f.int(proof.titles)],
                [t.intro.proofFirst(f.pct1(proof.llm)), f.pct1(proof.ours)],
                [t.intro.proofPersonal(f.pct1(proof.noQloo)), f.pct1(proof.personal)],
              ] as const).map(([label, value]) => (
                <div key={label} className="flex flex-col-reverse justify-end gap-2 rounded-3xl border border-line bg-card p-5 sm:p-6">
                  <dt className="text-sm text-muted">{label}</dt>
                  <dd className="font-display text-4xl text-accent sm:text-5xl">{value}</dd>
                </div>
              ))}
              <p className="text-xs text-muted sm:col-span-3">
                {t.intro.proofFoot} <a href="/method" className="underline">{t.intro.proofLink}</a>.
              </p>
            </dl>
          )}
        </section>
      )}

      {stage === "favourites" && <FavouritesStep value={favourites} onChange={(v) => {
        setFavourites(v);
        try { sessionStorage.setItem(SAVED, JSON.stringify({ favourites: v })); } catch { /* not saved */ }
      }} onNext={() => go("level")} />}
      {stage === "level" && <LevelStep variety={variety} onVariety={setVariety}
        onBack={() => go("favourites")} onDone={(v) => { setNote(null); start(v); }} />}
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
            <AgentRun events={events} running={false} level={2} />
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
            isSaved={(p) => !!profile?.list.some((s) => s.key === listKey(p))}
            onSave={(p) => updateProfile((prof) => toggleSaved(prof, p))}
            onShare={share}
            recordedAt={recordedAt}
            watchOn={watchOn}
          />
          {profile && <MyList profile={profile} onChange={setProfile} />}
          <WeeklyReminder profile={profile} />
        </>
      )}

      <section id="how" className="mt-28 border-t border-line pt-12">
        <h2 className="font-display text-3xl">{t.how.title}</h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {([[t.how.c1t, t.how.c1], [t.how.c2t, t.how.c2], [t.how.c3t, t.how.c3]] as const).map(([title, body], i) => (
            <div key={title} className="rounded-3xl border border-line bg-card p-6">
              <span className={`grid h-10 w-10 place-items-center rounded-2xl font-display text-lg ${["bg-accent text-accent-ink", "bg-good text-paper", "bg-later text-paper"][i]}`} aria-hidden>
                {i + 1}
              </span>
              <p className="mt-4 font-display text-xl">{title}</p>
              <p className="mt-2 text-muted">{body}</p>
            </div>
          ))}
        </div>
        <p className="mt-8 text-sm text-muted">
          {t.how.credits(<a className="underline" href="https://www.opensubtitles.org/">opensubtitles.org</a>)}
        </p>
      </section>

      </main>

      <footer className="mt-16 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6 text-sm text-muted">
        <p>{t.footer.built}</p>
        <nav className="flex gap-5">
          <a href="/method" className="hover:text-ink">{t.nav.method}</a>
          <a href="https://github.com/BriceZemba/comprende" className="hover:text-ink">{t.footer.source}</a>
        </nav>
      </footer>
    </div>
  );
}
