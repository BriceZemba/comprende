// Comprehension maths used by the app. Mirrors pipeline/comprende_pipeline/{coverage,vocab_test}.py;
// pipeline/fixtures/parity.json is generated from the Python code and checked against this file.

export type Band = [number, number];

export interface VocabItem {
  word: string;
  real: boolean;
  band?: Band;
}

export interface VocabEstimate {
  vocab_size: number;
  false_alarm_rate: number;
  reliable: boolean;
  bands: { band: Band; hit_rate: number; corrected: number }[];
}

const round = (x: number, d: number) => Math.round(x * 10 ** d) / 10 ** d;

// Yes/No test scoring (Meara & Buxton 1987): per-band hit rate corrected for guessing
// with the pseudoword false-alarm rate, scaled by band width. Missing answers count as "no".
export function estimateVocab(items: VocabItem[], answers: Record<string, boolean>, bands: Band[]): VocabEstimate {
  const fakes = items.filter((i) => !i.real);
  const falseAlarm = fakes.length ? fakes.filter((i) => answers[i.word]).length / fakes.length : 0;
  let total = 0;
  const perBand = bands.map(([lo, hi]) => {
    const inBand = items.filter((i) => i.real && i.band && i.band[0] === lo && i.band[1] === hi);
    const hits = inBand.filter((i) => answers[i.word]).length / inBand.length;
    const corrected = falseAlarm >= 1 ? 0 : Math.max(0, (hits - falseAlarm) / (1 - falseAlarm));
    total += corrected * (hi - lo + 1);
    return { band: [lo, hi] as Band, hit_rate: round(hits, 3), corrected: round(corrected, 3) };
  });
  return {
    vocab_size: Math.round(total),
    false_alarm_rate: round(falseAlarm, 3),
    reliable: falseAlarm <= 0.25,
    bands: perBand,
  };
}

// Linear interpolation of a title's stored coverage curve at any vocabulary size.
export function coverageAt(grid: number[], curve: number[], vocabSize: number): number {
  if (vocabSize <= grid[0]) return vocabSize > 0 ? (curve[0] * vocabSize) / grid[0] : 0;
  if (vocabSize >= grid[grid.length - 1]) return curve[curve.length - 1];
  const j = grid.findIndex((g) => g > vocabSize);
  const [x0, x1, y0, y1] = [grid[j - 1], grid[j], curve[j - 1], curve[j]];
  return y0 + ((y1 - y0) * (vocabSize - x0)) / (x1 - x0);
}

// Thresholds from the coverage literature (Hu & Nation 2000; Nation 2006).
export type Fit = "comfortable" | "watchable" | "stretch" | "later";

export function fitFor(coverage: number): Fit {
  if (coverage >= 0.98) return "comfortable";
  if (coverage >= 0.95) return "watchable";
  if (coverage >= 0.9) return "stretch";
  return "later";
}
