// Run: node --experimental-strip-types web/lib/reminder.test.ts
import { strict as assert } from "node:assert";
import { googleCalendarUrl, ics, nextOccurrence, type Reminder } from "./reminder.ts";

// Wednesday 28 Oct 2026, 10:00 local.
const now = new Date(2026, 9, 28, 10, 0);

// Friday 20:00 is two days ahead; Wednesday 20:00 is today; Wednesday 09:00 has passed, so next week.
assert.equal(nextOccurrence(5, 20, 0, now).toDateString(), new Date(2026, 9, 30).toDateString());
assert.equal(nextOccurrence(3, 20, 0, now).getDate(), 28);
assert.equal(nextOccurrence(3, 9, 0, now).getDate(), 4);

const r: Reminder = { day: 5, hour: 20, minute: 30, title: "Spanish film night", details: "Next: Hogar, then El hoyo; enjoy",
  url: "https://comprende.vercel.app/?from=reminder" };
const cal = ics(r, now, "test-uid@comprende");
assert.match(cal, /\r\nDTSTART:20261030T203000\r\n/);
assert.match(cal, /\r\nRRULE:FREQ=WEEKLY;BYDAY=FR\r\n/);
assert.match(cal, /SUMMARY:Spanish film night/);
assert.ok(cal.includes("Hogar\\, then El hoyo\\; enjoy"), "commas and semicolons are escaped");
const enc = new TextEncoder();
const long = ics({ ...r, details: "Próxima película: La sociedad de la nieve, El espíritu de la colmena, Ánimas Trujano, más títulos" }, now, "u");
assert.ok(long.split("\r\n").every((l) => enc.encode(l).length <= 75), "lines are folded at 75 octets, accents included");
assert.ok(long.replace(/\r\n /g, "").includes("Ánimas Trujano"), "unfolding restores the text");

const g = new URL(googleCalendarUrl(r, now, "Africa/Casablanca"));
assert.equal(g.searchParams.get("recur"), "RRULE:FREQ=WEEKLY;BYDAY=FR");
assert.equal(g.searchParams.get("dates"), "20261030T203000/20261030T223000");
assert.equal(g.searchParams.get("ctz"), "Africa/Casablanca");

console.log("reminder ok");
