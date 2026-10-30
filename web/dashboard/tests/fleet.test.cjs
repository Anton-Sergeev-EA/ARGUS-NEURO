'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {csvCell, rankingToCsv, PRIORITIES, TEXT, LANGUAGES} = require('../fleet.js');

test('every language translates the fleet page, the priorities and every reason code', () => {
  const html = fs.readFileSync(path.join(__dirname, '../fleet.html'), 'utf8');
  const keys = [...html.matchAll(/data-text="([^"]+)"/g)].map(m => m[1]);
  const dynamic = [...PRIORITIES.map(p => 'prio_' + p),
    'reason_below_service_threshold', 'reason_bms_alarm', 'reason_approaching_threshold',
    'reason_forecast_within_planning_horizon', 'reason_cell_imbalance', 'reason_no_comparable_measurements',
    'colBattery', 'colSoh', 'colMargin', 'colPriority', 'colReasons', 'colRemaining', 'fleetLimits', 'fleetError', 'fleetSummary'];
  for (const lang of LANGUAGES) {
    for (const key of [...keys, ...dynamic]) {
      assert.ok(TEXT[lang][key] && TEXT[lang][key].trim(), `${lang} ${key}`);
    }
  }
  assert.match(html, /<html lang="en">/);
});

test('exported CSV quotes separators and neutralizes spreadsheet formulas', () => {
  assert.equal(csvCell('a,b'), '"a,b"');
  assert.equal(csvCell('say "hi"'), '"say ""hi"""');
  assert.equal(csvCell('=HYPERLINK("http://x")'), '"\'=HYPERLINK(""http://x"")"');
  assert.equal(csvCell('-1+1'), "'-1+1");
  assert.equal(csvCell(null), '');
  assert.equal(csvCell(12.5), '12.5');
});

test('ranking export keeps one line per battery and tolerates missing forecasts', () => {
  const rows = [
    {battery_id: 'S-1', priority: 'service_now', reasons: ['below_service_threshold'], soh_pct: 60, service_threshold_pct: 70, margin_points: -10, remaining_equivalent_cycles: null},
    {battery_id: '=bad', priority: 'monitor', reasons: [], soh_pct: 99, service_threshold_pct: 70, margin_points: 29, remaining_equivalent_cycles: [100, 300]},
  ];
  const lines = rankingToCsv(rows).trim().split('\n');
  assert.equal(lines.length, 3);
  assert.equal(lines[1], 'S-1,service_now,below_service_threshold,60,70,-10,,');
  assert.ok(lines[2].startsWith("'=bad,monitor,,99,70,29,100,300"));
  assert.ok(rankingToCsv(rows, key => TEXT.en[key]).includes('Service now'));
});

test('the sample fleet table parses and covers several priorities', () => {
  const text = fs.readFileSync(path.join(__dirname, '../fleet-example.csv'), 'utf8').trim().split('\n');
  assert.equal(text[0], 'battery_id,equivalent_cycles,capacity_ah,reference_capacity_ah,condition_id,data_origin');
  assert.ok(new Set(text.slice(1).map(l => l.split(',')[0])).size >= 10);
  assert.ok(text.slice(1).every(l => l.endsWith(',synthetic')));
});
