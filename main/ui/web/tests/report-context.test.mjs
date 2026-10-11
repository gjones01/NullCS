import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { signalBand, scoreBin } from '../src/lib/report-context.ts';
const reference = JSON.parse(readFileSync(new URL('../src/lib/score-reference.json', import.meta.url)));
test('only supported raw scores receive tested display bands', () => {
  for (const x of [null, NaN, Infinity, -0.01, 1.01]) assert.equal(signalBand(x, true), 'unavailable');
  assert.equal(signalBand(.99, false), 'unavailable');
  assert.equal(signalBand(0, true), 'low'); assert.equal(signalBand(.19999, true), 'low');
  assert.equal(signalBand(.2, true), 'elevated'); assert.equal(signalBand(.49999, true), 'elevated');
  assert.equal(signalBand(.5, true), 'strong'); assert.equal(signalBand(1, true), 'strong');
});
test('histogram includes boundary scores and preserves source counts', () => {
  assert.equal(scoreBin(0), 0); assert.equal(scoreBin(1), 19); assert.equal(scoreBin(.5), 10);
  assert.equal(scoreBin(NaN), null); assert.equal(scoreBin(-1), null);
  assert.equal(reference.negative_counts.reduce((a,b)=>a+b,0), reference.negative);
  assert.equal(reference.positive_counts.reduce((a,b)=>a+b,0), reference.positive);
  assert.equal(reference.negative + reference.positive, reference.rows);
  for (const t of reference.thresholds) {
    assert.equal(t.tp+t.fn,reference.positive); assert.equal(t.fp+t.tn,reference.negative);
  }
});
