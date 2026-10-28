"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import type { Profile } from "@/lib/profile";
import { googleCalendarUrl, type Reminder } from "@/lib/reminder";

const ORDER = [1, 2, 3, 4, 5, 6, 0]; // Monday first

// "Your next film", once a week: the learner picks a day and an hour, and Google Calendar opens with a repeating
// event ready to save. The calendar does the reminding (no account with us, no notification permission, nothing
// sent to us); the event links back to Comprende, which shows the next saved film and what came within reach.
export default function WeeklyReminder({ profile }: { profile: Profile | null }) {
  const { t, lang } = useI18n();
  const r = t.reminder;
  const [day, setDay] = useState(5);
  const [time, setTime] = useState("20:00");
  const [done, setDone] = useState(false);

  const dayName = (d: number) =>
    new Intl.DateTimeFormat(lang, { weekday: "long" }).format(new Date(2026, 10, 1 + d)); // 1 Nov 2026 is a Sunday
  const next = profile?.list.find((s) => !s.watched)?.name;
  const build = (): Reminder => {
    const [hour, minute] = time.split(":").map(Number);
    return { day, hour: hour || 0, minute: minute || 0, title: r.event, details: next ? r.next(next) : r.generic,
             url: `${window.location.origin}/?from=reminder` };
  };
  const google = () => {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    window.open(googleCalendarUrl(build(), new Date(), zone), "_blank", "noopener");
    setDone(true);
  };

  return (
    <section id="reminder" aria-labelledby="reminder-title" className="rise mt-10 scroll-mt-6 max-w-2xl rounded-3xl border border-line bg-card p-5 sm:p-6">
      <h3 id="reminder-title" className="font-display text-2xl">{r.title}</h3>
      <p className="mt-1 text-sm text-muted">{next ? r.leadNext(next) : r.lead}</p>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="block text-muted">{r.day}</span>
          <select value={day} onChange={(e) => { setDay(Number(e.target.value)); setDone(false); }}
            className="mt-1 min-h-11 rounded-xl border border-line bg-paper px-3 capitalize">
            {ORDER.map((d) => <option key={d} value={d}>{dayName(d)}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="block text-muted">{r.time}</span>
          <input type="time" value={time} onChange={(e) => { setTime(e.target.value); setDone(false); }}
            className="mt-1 min-h-11 rounded-xl border border-line bg-paper px-3" />
        </label>
        <button type="button" onClick={google}
          className="min-h-11 rounded-full bg-accent px-5 font-medium text-accent-ink hover:brightness-110">
          {r.google}
        </button>
      </div>
      {done && <p className="rise mt-3 text-sm text-good" role="status">{r.done(dayName(day), time)}</p>}
      <p className="mt-3 text-xs text-muted">{r.privacy}</p>
    </section>
  );
}
