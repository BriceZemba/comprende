// A weekly "your next film" reminder, as a calendar event the learner adds themself (.ics file, or a
// Google Calendar link). No server, no account, no notification permission: the calendar does the
// reminding, on any phone or computer, and nothing about the learner leaves the device.

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

// Local "floating" time (no zone): the calendar shows it at that hour wherever the learner is.
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

// RFC 5545 text: escape backslash, semicolon, comma and newlines.
const text = (s: string) => s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");

// Lines longer than 75 octets are folded (a continuation line starts with one space). Count UTF-8 bytes,
// so French and Spanish accents never push a line over.
const enc = new TextEncoder();
function fold(line: string): string {
  const parts: string[] = [];
  let cur = "", bytes = 0;
  for (const ch of line) {
    const n = enc.encode(ch).length;
    if (bytes + n > (parts.length ? 74 : 75)) { parts.push(cur); cur = ""; bytes = 0; }
    cur += ch; bytes += n;
  }
  parts.push(cur);
  return parts.join("\r\n ");
}

export function ics(r: Reminder, now: Date, uid: string): string {
  const start = nextOccurrence(r.day, r.hour, r.minute, now);
  const end = new Date(start.getTime() + 2 * 60 * 60 * 1000);
  const utc = now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  return [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Comprende//Weekly film//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
    "BEGIN:VEVENT", `UID:${uid}`, `DTSTAMP:${utc}`, `DTSTART:${stamp(start)}`, `DTEND:${stamp(end)}`,
    `RRULE:FREQ=WEEKLY;BYDAY=${DAYS[r.day]}`,
    `SUMMARY:${text(r.title)}`, `DESCRIPTION:${text(`${r.details}\n${r.url}`)}`, `URL:${r.url}`,
    "BEGIN:VALARM", "ACTION:DISPLAY", `DESCRIPTION:${text(r.title)}`, "TRIGGER:PT0M", "END:VALARM",
    "END:VEVENT", "END:VCALENDAR", "",
  ].map(fold).join("\r\n");
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
