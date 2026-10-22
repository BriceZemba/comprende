// Checks the TypeScript port against outputs of the Python pipeline.
// Run: node --experimental-strip-types web/lib/comprehension.parity.test.ts
import { readFileSync } from "node:fs";
import { strict as assert } from "node:assert";
import { coverageAt, estimateVocab, fitFor, type Band, type VocabItem } from "./comprehension.ts";

const fx = JSON.parse(readFileSync(new URL("../../pipeline/fixtures/parity.json", import.meta.url), "utf-8"));
const items: VocabItem[] = fx.items;
const bands: Band[] = fx.bands;

for (const c of fx.vocab_cases) {
  assert.deepEqual(estimateVocab(items, c.answers, bands), c.expected);
}
for (const c of fx.coverage_cases) {
  const got = coverageAt(fx.grid, c.curve, c.vocab);
  assert.ok(Math.abs(got - c.expected) < 1e-9, `coverage ${got} != ${c.expected}`);
  assert.equal(fitFor(got), c.fit);
}
console.log(`parity ok: ${fx.vocab_cases.length} vocab cases, ${fx.coverage_cases.length} coverage cases`);
