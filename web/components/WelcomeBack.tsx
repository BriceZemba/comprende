"use client";

import { useI18n } from "@/lib/i18n";
import { unlocked, type Profile } from "@/lib/profile";

// Shown on the home page to a learner who has been here before: where they stand, what opened up,
// and one button for fresh picks at their current level.
export default function WelcomeBack({ profile, onFresh, onForget }: {
  profile: Profile;
  onFresh: () => void;
  onForget: () => void;
}) {
  const { t, f } = useI18n();
  const watched = profile.list.filter((s) => s.watched).length;
  const opened = unlocked(profile, profile.shownAtVocab, profile.vocab);
  const held = profile.heldBack;
  const toGo = held?.vocab_for_95 ? held.vocab_for_95 - profile.vocab : null;
  return (
    <section className="rise mt-4 rounded-3xl border border-accent/40 bg-card p-5 sm:p-6" aria-labelledby="welcome-back">
      <h2 id="welcome-back" className="font-display text-2xl sm:text-3xl">{t.welcome.title}</h2>
      <ul className="mt-3 space-y-1.5 text-sm sm:text-base">
        <li>{t.welcome.level(f.int(profile.vocab))}</li>
        {profile.list.length > 0 && <li>{t.welcome.list(profile.list.length, watched)}</li>}
        {opened > 0 && <li className="font-medium text-good">{t.welcome.opened(opened)}</li>}
        {held && toGo !== null && (
          <li>{toGo <= 0 ? t.welcome.heldReady(held.name) : t.welcome.held(held.name, f.int(Math.ceil(toGo / 50) * 50))}</li>
        )}
      </ul>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" onClick={onFresh}
          className="rounded-full bg-accent px-6 py-3 font-medium text-accent-ink shadow-sm hover:brightness-110">
          {t.welcome.fresh}
        </button>
        <button type="button" onClick={onForget} className="text-sm text-muted underline">{t.welcome.forget}</button>
      </div>
      <p className="mt-3 text-xs text-muted">{t.welcome.device}</p>
    </section>
  );
}
