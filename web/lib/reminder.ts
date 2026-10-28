// A weekly "your next film" reminder, as a repeating Google Calendar event the learner saves themself.
// No server, no account with us, no notification permission: the calendar does the reminding, and nothing
// about the learner leaves the device except what they choose to save in their own calendar.

export const DAYS = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"] as const; // index = Date.getDay()

export interface Reminder {
  day: number; // 0 = Sunday … 6 = Saturday
  hour: number;
  minute: number;
  title: string;
  details: string;
  url: string;
}

const pad = (n: number) => String(n).padStart(2, "0");

// Local time without a zone; Google Calendar reads it in the zone passed as ctz.
const stamp = (d: Date) =>
  `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}T${pad(d.getHours())}${pad(d.getMinutes())}00`;

// The next time that weekday and hour come round, from `now` (today counts if the hour is still ahead).
export function nextOccurrence(day: number, hour: number, minute: number, now: Date): Date {
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, minute);
  let ahead = (day - now.getDay() + 7) % 7;
  if (ahead === 0 && d <= now) ahead = 7;
  d.setDate(d.getDate() + ahead);
  return d;
}

export function googleCalendarUrl(r: Reminder, now: Date, timeZone: string): string {
  const start = nextOccurrence(r.day, r.hour, r.minute, now);
  const end = new Date(start.getTime() + 2 * 60 * 60 * 1000);
  const q = new URLSearchParams({
    action: "TEMPLATE", text: r.title, details: `${r.details}\n${r.url}`,
    dates: `${stamp(start)}/${stamp(end)}`, recur: `RRULE:FREQ=WEEKLY;BYDAY=${DAYS[r.day]}`, ctz: timeZone,
  });
  return `https://calendar.google.com/calendar/render?${q}`;
}
