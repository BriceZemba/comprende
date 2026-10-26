"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { markWatched, unlocked, type Profile, type Verdict } from "@/lib/profile";

const VERDICTS: Verdict[] = ["easy", "ok", "hard"];

// Saved titles, and the loop that brings a learner back: after a film, "how was it?" moves the level,
// and the list says how many titles that opened up.
export default function MyList({ profile, onChange }: { profile: Profile; onChange: (p: Profile) => void }) {
  const { t, f } = useI18n();
  const [asking, setAsking] = useState<string | null>(null);
  const [news, setNews] = useState<string | null>(null);
  if (profile.list.length === 0) return null;

  const answer = (key: string, verdict: Verdict) => {
    const next = markWatched(profile, key, verdict);
    const opened = unlocked(next, profile.vocab, next.vocab);
    setNews([t.list.levelNow(f.int(next.vocab), f.int(profile.vocab)), opened > 0 ? t.list.unlocked(opened) : ""]
      .filter(Boolean).join(" "));
    setAsking(null);
    onChange(next);
  };

  return (
    <section className="rise mt-10" aria-labelledby="my-list">
      <h3 id="my-list" className="font-display text-2xl">{t.list.title} <span className="text-muted">({profile.list.length})</span></h3>
      <p className="text-sm text-muted">{t.list.lead}</p>
      {news && <p className="rise mt-3 max-w-2xl rounded-2xl bg-good-soft p-3 text-sm" role="status">{news}</p>}
      <ul className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {profile.list.map((s) => (
          <li key={s.key} className="flex min-w-0 items-center gap-3 rounded-2xl border border-line bg-card p-3">
            <div className="h-14 w-10 shrink-0 overflow-hidden rounded-md bg-line">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              {s.image ? <img src={s.image} alt="" className="h-full w-full object-cover" loading="lazy" /> : null}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium" lang="es">{s.name}{s.year ? <span className="text-muted"> · {s.year}</span> : null}</p>
              {s.watched ? (
                <p className="text-xs text-good">{t.list.watched(t.list.verdicts[s.watched.verdict])}</p>
              ) : asking === s.key ? (
                <div className="mt-1 flex flex-wrap items-center gap-1.5" role="group" aria-label={t.list.howWas(s.name)}>
                  {VERDICTS.map((v) => (
                    <button key={v} type="button" onClick={() => answer(s.key, v)}
                      className="min-h-9 rounded-full border border-line px-3 py-1 text-xs hover:border-ink">
                      {t.list.verdicts[v]}
                    </button>
                  ))}
                </div>
              ) : (
                <button type="button" onClick={() => setAsking(s.key)} className="mt-0.5 text-xs text-accent underline">
                  {t.list.didWatch}
                </button>
              )}
            </div>
            <button type="button" aria-label={t.list.remove(s.name)} title={t.list.remove(s.name)}
              onClick={() => onChange({ ...profile, list: profile.list.filter((x) => x.key !== s.key) })}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-muted hover:text-ink">×</button>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted">{t.list.note}</p>
    </section>
  );
}
