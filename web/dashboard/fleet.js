'use strict';
const {TEXT, LANGUAGES} = typeof module !== 'undefined' ? require('./battery-i18n.js') : BATTERY_I18N;

const PRIORITIES = ['service_now', 'plan_service', 'monitor', 'insufficient_data'];

/** CSV field quoting that also blocks spreadsheet formula injection in exported text. */
function csvCell(value) {
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : '';
  let text = value === null || value === undefined ? '' : String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = "'" + text;
  return /[",\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
}

function rankingToCsv(rows, label) {
  const header = ['battery_id', 'priority', 'reasons', 'soh_pct', 'service_threshold_pct', 'margin_points', 'remaining_cycles_low', 'remaining_cycles_high'];
  const lines = [header.join(',')];
  rows.forEach(row => {
    const cycles = row.remaining_equivalent_cycles || [null, null];
    lines.push([row.battery_id, label ? label('prio_' + row.priority) : row.priority, row.reasons.join(' | '), row.soh_pct, row.service_threshold_pct, row.margin_points, cycles[0], cycles[1]].map(csvCell).join(','));
  });
  return lines.join('\n') + '\n';
}

if (typeof module !== 'undefined') module.exports = {csvCell, rankingToCsv, PRIORITIES, TEXT, LANGUAGES};

if (typeof document !== 'undefined') {
  const $ = id => document.getElementById(id);
  let lang = 'en';
  let last = null;
  try { const saved = localStorage.getItem('argus.lang'); if (LANGUAGES.includes(saved)) lang = saved; } catch { /* default */ }
  const t = key => TEXT[lang][key] || TEXT.en[key] || key;

  function cell(row, text, className) {
    const node = document.createElement('td');
    node.textContent = text;
    if (className) node.className = className;
    row.append(node);
  }

  function render() {
    if (!last) return;
    $('results').hidden = false;
    const counts = $('counts');
    counts.replaceChildren();
    PRIORITIES.forEach(priority => {
      const card = document.createElement('article');
      const title = document.createElement('h3');
      title.textContent = t('prio_' + priority);
      const value = document.createElement('p');
      value.className = 'big';
      value.textContent = String(last.counts[priority]);
      card.append(title, value);
      counts.append(card);
    });
    const table = $('ranking');
    table.replaceChildren();
    const head = document.createElement('tr');
    ['colBattery', 'colPriority', 'colSoh', 'colMargin', 'colRemaining', 'colReasons'].forEach(key => {
      const th = document.createElement('th');
      th.textContent = t(key);
      head.append(th);
    });
    table.append(head);
    const number = value => value === null || value === undefined ? '—' : value.toLocaleString(lang);
    last.rows.forEach(row => {
      const tr = document.createElement('tr');
      cell(tr, row.battery_id);
      cell(tr, t('prio_' + row.priority), 'prio ' + row.priority);
      cell(tr, number(row.soh_pct));
      cell(tr, number(row.margin_points));
      const cycles = row.remaining_equivalent_cycles;
      cell(tr, cycles ? [...new Set(cycles.map(number))].join('–') + (row.measurement_scope === 'pack' && row.forecast_interval_kind !== 'empirically_calibrated_cell_level' ? ' *' : '') : '—');
      cell(tr, row.reasons.map(code => t('reason_' + code)).join('; ') || '—');
      table.append(tr);
    });
    $('limits').textContent = t('fleetLimits') + ' ' + t('fleetUncalibrated');
    $('message').textContent = last.batteries.toLocaleString(lang) + ' ' + t('fleetSummary');
  }

  function localize() {
    document.documentElement.lang = lang;
    document.title = 'ARGUS-NEURO · ' + t('fleetNav');
    $('language').value = lang;
    document.querySelectorAll('[data-text]').forEach(node => { node.textContent = t(node.dataset.text); });
    render();
  }

  $('language').addEventListener('change', () => {
    lang = $('language').value;
    try { localStorage.setItem('argus.lang', lang); } catch { /* ignore */ }
    localize();
  });

  $('fleet-form').addEventListener('submit', async event => {
    event.preventDefault();
    const file = $('fleet-file').files[0];
    if (!file) return;
    $('rank').disabled = true;
    try {
      if (file.size > 2000000) throw new Error('large');
      const plan = $('plan').value.trim();
      const query = '?use_case=' + encodeURIComponent($('use-case').value) + (plan ? '&plan_within_cycles=' + encodeURIComponent(plan) : '');
      const response = await fetch('/api/battery/fleet-csv' + query, {
        method: 'POST', headers: {'Content-Type': 'text/csv'}, body: await file.text(), signal: AbortSignal.timeout(120000),
      });
      if (!response.ok) throw new Error('request_failed');
      last = await response.json();
      render();
    } catch {
      last = null;
      $('results').hidden = true;
      $('message').textContent = t('fleetError');
    } finally {
      $('rank').disabled = false;
    }
  });

  $('download').addEventListener('click', () => {
    if (!last) return;
    const url = URL.createObjectURL(new Blob([rankingToCsv(last.rows, t)], {type: 'text/csv'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'fleet-ranking.csv';
    link.click();
    URL.revokeObjectURL(url);
  });

  localize();
}
