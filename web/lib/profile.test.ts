// Run: node --experimental-strip-types web/lib/profile.test.ts
import { strict as assert } from "node:assert";
import { adjustVocab, markWatched, unlocked, type Profile } from "./profile.ts";

// Level moves a little after each film, rounded to 50, within the word check's range.
assert.equal(adjustVocab(3000, "ok"), 3100);
assert.equal(adjustVocab(3000, "easy"), 3300);
assert.equal(adjustVocab(3000, "hard"), 2550);
assert.equal(adjustVocab(11900, "easy"), 12000);
assert.equal(adjustVocab(550, "hard"), 500);

// Titles that cross 95% coverage between two levels are counted as newly within reach.
const grid = [1000, 2000, 3000, 4000];
const profile: Profile = {
  favourites: [], vocab: 3000, shownAtVocab: 3000, heldBack: null, lastVisit: "",
  list: [{ key: "Q1", name: "Celda 211", kind: "film", year: 2009, image: null, vocab_for_95: 3200, savedAt: "" }],
  map: { grid, titles: [
    { key: "a", curve: [0.90, 0.93, 0.94, 0.96] },  // opens between 3000 and 4000
    { key: "b", curve: [0.95, 0.96, 0.97, 0.98] },  // already comfortable
    { key: "c", curve: [0.80, 0.85, 0.88, 0.90] },  // still too hard
  ] },
};
assert.equal(unlocked(profile, 3000, 4000), 1);
assert.equal(unlocked(profile, 4000, 3000), 0);

const after = markWatched(profile, "Q1", "easy");
assert.equal(after.vocab, 3300);
assert.equal(after.list[0].watched?.verdict, "easy");
assert.equal(profile.list[0].watched, undefined);  // the old profile is not changed
console.log("profile ok");
