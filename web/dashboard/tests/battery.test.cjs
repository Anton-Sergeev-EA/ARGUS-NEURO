'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {TEXT, ADVICE, LANGUAGES, trendCoordinates} = require('../battery.js');

test('all nine languages cover visible labels, errors, forecast states and guidance', () => {
  assert.deepEqual(LANGUAGES, ['en','ru','zh','hi','es','fr','de','ja','it']);
  const keys = Object.keys(TEXT.en).sort();
  const codes = Object.keys(ADVICE.en).sort();
  for (const lang of LANGUAGES) {
    assert.deepEqual(Object.keys(TEXT[lang]).sort(), keys, lang);
    assert.deepEqual(Object.keys(ADVICE[lang]).sort(), codes, lang);
    assert.ok(Object.values(TEXT[lang]).every(v => typeof v === 'string' && v.trim()));
    for (const entry of Object.values(ADVICE[lang])) {
      assert.equal(entry.length, 3);
      assert.ok(entry.every(v => typeof v === 'string' && v.trim()));
    }
  }
  const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
  for (const match of html.matchAll(/data-text="([^"]+)"/g)) {
    assert.ok(keys.includes(match[1]), match[1]);
  }
  assert.match(html, /<html lang="en">/);
  const options = [...html.matchAll(/<option value="([a-z]{2})" lang=/g)].map(m => m[1]);
  assert.deepEqual(options, LANGUAGES);
});

test('a single capacity record produces a visible, finite chart point', () => {
  assert.deepEqual(trendCoordinates([], 80), []);
  const point = trendCoordinates([{equivalent_cycles: 0, soh_pct: 95}], 80);
  assert.equal(point.length, 1);
  assert.ok(point[0].every(Number.isFinite));
});

test('changing the cycle origin does not distort relative chart positions', () => {
  const history = [{equivalent_cycles: 10, soh_pct: 100}, {equivalent_cycles: 100, soh_pct: 92}];
  const shifted = history.map(r => ({...r, equivalent_cycles:r.equivalent_cycles+10000}));
  assert.deepEqual(trendCoordinates(history, 80), trendCoordinates(shifted, 80));
});

const {forecastShape, makeScale} = require('../battery.js');
const flat = [{equivalent_cycles: 0, soh_pct: 100}, {equivalent_cycles: 100, soh_pct: 90}];

test('forecast wedge runs from the last point to the threshold at both interval ends', () => {
  const shape = forecastShape(flat, 80, {status: 'conditional_estimate', equivalent_cycles: [100, 300]}, 1000);
  assert.deepEqual(shape.start, {cycle: 100, soh: 90});
  assert.equal(shape.lowEdge.cycle, 200);
  assert.ok(Math.abs(shape.lowEdge.soh - 80) < 1e-9);
  assert.equal(shape.highEdge.cycle, 400);
  assert.ok(Math.abs(shape.highEdge.soh - 80) < 1e-9);
  assert.equal(shape.clipped, false);
});

test('a very long forecast is cut at the cap without leaving the threshold line', () => {
  const shape = forecastShape(flat, 80, {status: 'conditional_estimate', equivalent_cycles: [100, 1000]}, 150);
  assert.equal(shape.clipped, true);
  assert.equal(shape.highEdge.cycle, 250);
  assert.ok(shape.highEdge.soh > 80 && shape.highEdge.soh < 90);
  assert.equal(shape.extraX, 150);
});

test('no wedge without a numeric estimate or when the threshold is already reached', () => {
  assert.equal(forecastShape(flat, 80, {status: 'insufficient_history', equivalent_cycles: null}, 1000), null);
  assert.equal(forecastShape(flat, 95, {status: 'conditional_estimate', equivalent_cycles: [1, 2]}, 1000), null);
  assert.equal(forecastShape([], 80, {status: 'conditional_estimate', equivalent_cycles: [1, 2]}, 1000), null);
});

test('previous and current series share one scale and stay inside the plot', () => {
  const previous = [{equivalent_cycles: 0, soh_pct: 70}, {equivalent_cycles: 400, soh_pct: 60}];
  const scale = makeScale([flat, previous], 50, 100);
  for (const row of [...flat, ...previous]) {
    assert.ok(scale.x(row.equivalent_cycles) >= 55 && scale.x(row.equivalent_cycles) <= 875);
    assert.ok(scale.y(row.soh_pct) >= 40 && scale.y(row.soh_pct) <= 260);
  }
});
