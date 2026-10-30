'use strict';
const {TEXT, ADVICE, LANGUAGES} = typeof module !== 'undefined' ? require('./battery-i18n.js') : BATTERY_I18N;

/* ---------- Chart geometry (pure functions, covered by tests) ---------- */

const PLOT = {left: 55, right: 875, top: 40, bottom: 260};

/** Scale shared by every series on the chart: observed history, forecast, previous run. */
function makeScale(series, threshold, extraX = 0) {
  const rows = series.flat();
  const xs = rows.map(r => r.equivalent_cycles);
  const ys = rows.map(r => r.soh_pct);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs) + extraX;
  const minY = Math.min(threshold, ...ys) - 3;
  const maxY = Math.max(100, ...ys) + 3;
  return {
    minX, maxX, minY, maxY,
    x: value => PLOT.left + ((value - minX) / Math.max(1, maxX - minX)) * (PLOT.right - PLOT.left),
    y: value => PLOT.bottom - ((value - minY) / (maxY - minY)) * (PLOT.bottom - PLOT.top),
  };
}

function trendCoordinates(history, threshold) {
  if (!history.length) return [];
  const scale = makeScale([history], threshold);
  return history.map(row => [scale.x(row.equivalent_cycles), scale.y(row.soh_pct)]);
}

/**
 * Remaining-life range drawn as a wedge from the last measurement to the threshold.
 * Both edges are straight lines to the cycle counts where the threshold is reached;
 * the drawing is cut off at `cap` cycles so a very long forecast stays readable.
 */
function forecastShape(history, threshold, rul, cap) {
  const last = history.at(-1);
  if (!last || !rul || rul.status !== 'conditional_estimate' || !rul.equivalent_cycles) return null;
  const [low, high] = rul.equivalent_cycles;
  if (last.soh_pct <= threshold || high <= 0) return null;
  const reach = Math.min(high, cap);
  const along = (cycles, distance) => ({
    cycle: last.equivalent_cycles + distance,
    soh: last.soh_pct + ((threshold - last.soh_pct) * distance) / cycles,
  });
  const lowEdge = along(Math.max(low, 1e-9), Math.min(Math.max(low, 1e-9), cap));
  const highEdge = along(high, reach);
  return {
    start: {cycle: last.equivalent_cycles, soh: last.soh_pct},
    lowEdge, highEdge,
    middle: along((low + high) / 2 || high, Math.min((low + high) / 2 || high, cap)),
    extraX: reach,
    clipped: high > cap,
  };
}

function formatRange(values, lang) {
  const rounded = values.map(v => Math.round(v * 10) / 10);
  if (rounded[0] === rounded[1]) return '≈ ' + rounded[0].toLocaleString(lang);
  return rounded.map(v => v.toLocaleString(lang)).join('–');
}

if (typeof module !== 'undefined') {
  module.exports = {trendCoordinates, makeScale, forecastShape, formatRange, TEXT, ADVICE, LANGUAGES};
}

/* ---------- Page behaviour (browser only) ---------- */

if (typeof document !== 'undefined') {
  const $ = id => document.getElementById(id);
  const state = {
    lang: 'en', records: [], origin: 'user_supplied', last: null, previous: null,
    payload: null, busy: false, scope: 'pack', axis: 'equivalent_cycles', datasetId: null,
  };
  try {
    const saved = localStorage.getItem('argus.lang');
    if (LANGUAGES.includes(saved)) state.lang = saved;
  } catch { /* storage may be blocked; English is the default */ }

  const t = key => TEXT[state.lang][key] || key;
  const message = key => { $('message').textContent = t(key); };
  const number = id => {
    const raw = $(id).value.trim();
    return raw === '' ? null : Number(raw);
  };

  function addText(parent, tag, text, className) {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    parent.append(node);
    return node;
  }

  function localize() {
    document.documentElement.lang = state.lang;
    document.title = 'ARGUS-NEURO · ' + t('battery');
    document.querySelector('nav').setAttribute('aria-label', t('navigation'));
    $('language').value = state.lang;
    document.querySelectorAll('[data-text]').forEach(node => { node.textContent = t(node.dataset.text); });
    document.querySelectorAll('[data-hint]').forEach(node => {
      const text = t(node.dataset.hint);
      node.dataset.tip = text;
      node.setAttribute('aria-label', text);
    });
    if (state.origin === 'synthetic' || state.origin === 'laboratory') {
      $('file-status').textContent = t(state.origin === 'synthetic' ? 'synthetic' : 'laboratory');
    }
    if (state.last) render(state.last);
  }

  /* ----- request building and transport ----- */

  function makePayload() {
    const source = $('limit-source').value.trim();
    const limitFields = ['min-temp', 'max-temp', 'spread-limit'];
    if (!source && limitFields.some(id => number(id) !== null)) throw new Error('limit_source_required');
    const profile = {
      battery_id: $('battery-id').value,
      application: $('application').value,
      chemistry: $('chemistry').value,
      measurement_scope: state.scope,
      cycle_axis: state.axis,
      reference_capacity_ah: number('reference'),
      reference_condition_id: $('condition').value,
      service_threshold_pct: number('threshold'),
      service_margin_pct: number('margin') ?? 5,
      equivalent_cycles_per_month: number('rate'),
    };
    if (source) {
      profile.limits = {
        source,
        charge_min_c: number('min-temp'),
        charge_max_c: number('max-temp'),
        cell_spread_limit_mv: number('spread-limit'),
      };
    }
    return {
      dataset_id: state.datasetId,
      data_origin: state.origin,
      profile,
      records: state.records,
      bms: {
        soc_pct: number('soc'),
        temperature_c: number('temperature'),
        cell_spread_mv: number('spread'),
        charging: $('charging').checked,
        safety_alarm: $('alarm').checked,
        high_soc_hot_storage_reported: $('hot-storage').checked,
        frequent_fast_charging_reported: $('fast-charging').checked,
      },
    };
  }

  async function call(path, body, contentType = 'application/json') {
    const options = body === undefined ? {} : {
      method: 'POST',
      headers: {'Content-Type': contentType},
      body: typeof body === 'string' ? body : JSON.stringify(body),
    };
    const response = await fetch('/api/battery/' + path, {...options, signal: AbortSignal.timeout(30000)});
    if (!response.ok) throw new Error('request_failed');
    return response.json();
  }

  function setBusy(value) {
    state.busy = value;
    const controls = '#battery-form input, #battery-form select, #battery-form button, #save, #saved, #public-example, #public-cell, #public-count';
    document.querySelectorAll(controls).forEach(node => { node.disabled = value; });
    if (!value && state.datasetId) {
      ['application', 'reference', 'condition', 'chemistry', 'rate', 'battery-id'].forEach(id => { $(id).disabled = true; });
    }
  }

  function markStale() {
    if (state.last) state.previous = state.last;
    state.last = null;
    $('results').hidden = true;
    message('stale');
  }

  function fillHistory(data) {
    state.records = data.records;
    state.origin = data.data_origin;
    state.scope = data.profile.measurement_scope;
    state.axis = data.profile.cycle_axis || 'equivalent_cycles';
    state.datasetId = data.dataset_id || null;
    const fields = {
      'battery-id': data.profile.battery_id,
      reference: data.profile.reference_capacity_ah,
      threshold: data.profile.service_threshold_pct,
      margin: data.profile.service_margin_pct ?? 5,
      condition: data.profile.reference_condition_id,
      rate: data.profile.equivalent_cycles_per_month ?? '',
      application: data.profile.application,
      chemistry: data.profile.chemistry,
      soc: data.bms?.soc_pct ?? '',
    };
    Object.entries(fields).forEach(([id, value]) => { $(id).value = value; });
    ['temperature', 'spread', 'limit-source', 'min-temp', 'max-temp', 'spread-limit'].forEach(id => { $(id).value = ''; });
    ['charging', 'alarm', 'hot-storage', 'fast-charging'].forEach(id => { $(id).checked = false; });
    $('file-status').textContent = t(state.origin === 'laboratory' ? 'laboratory' : 'synthetic');
  }

  async function analyze(payload) {
    state.payload = payload;
    const report = await call('analyze', payload);
    if (state.last && state.last.assessment_id !== report.assessment_id) state.previous = state.last;
    state.last = report;
    render(state.last);
    $('message').textContent = '';
  }

  async function analyzeLoaded(data) {
    fillHistory(data);
    await analyze(makePayload());
  }

  /* ----- rendering ----- */

  function render(data) {
    $('results').hidden = false;
    const sourceKey = data.source === 'synthetic' ? 'synthetic' : data.source === 'laboratory' ? 'laboratory' : 'uploaded';
    $('origin').textContent = t(sourceKey) + (data.measurement_scope === 'cell' ? ' ' + t('cellScope') : '');
    $('soh-value').textContent = data.soh_pct === null ? t('missing') : data.soh_pct.toLocaleString(state.lang) + '%';
    $('soh-note').textContent = t('capacityNote');
    $('soc-value').textContent = data.soc_pct === null ? t('missing') : data.soc_pct.toLocaleString(state.lang) + '%';
    renderRemainingLife(data);
    renderSecondOpinion(data);
    $('safety').textContent = t(data.safety_state === 'attention' ? 'safetyAlert' : 'safety');
    $('safety').className = data.safety_state === 'attention' ? 'warning' : 'note';
    renderTrend(data);
    chart(data);
    advice(data);
    renderDataset(data);
    $('saved-list').replaceChildren();
  }

  function renderRemainingLife(data) {
    const rul = data.rul;
    const unit = t(data.cycle_axis === 'equivalent_cycles' ? 'cycles' : 'tests');
    $('rul-value').textContent = rul.equivalent_cycles
      ? formatRange(rul.equivalent_cycles, state.lang) + ' ' + unit : t('missing');
    const months = rul.months ? ' ' + formatRange(rul.months, state.lang) + ' ' + t('months') + '.' : '';
    $('rul-note').textContent = t(rul.status === 'conditional_estimate' ? 'estimate' : rul.status) + months;
  }

  function renderSecondOpinion(data) {
    const node = $('second-opinion');
    const opinion = data.second_opinion;
    node.hidden = !opinion || opinion.status !== 'ok';
    if (node.hidden) return;
    const unit = t(data.cycle_axis === 'equivalent_cycles' ? 'cycles' : 'tests');
    const value = opinion.interval_cycles ? formatRange(opinion.interval_cycles, state.lang) : '≈ ' + opinion.equivalent_cycles.toLocaleString(state.lang);
    node.textContent = t('secondOpinion') + ' ' + value + ' ' + unit + '.';
  }

  function renderTrend(data) {
    const trend = data.trend;
    const unit = t(data.cycle_axis === 'equivalent_cycles' ? 'cycles' : 'tests');
    const node = $('trend-note');
    if (trend.change_pct_points === undefined) {
      node.textContent = t('trendUnclear');
    } else {
      const span = trend.from_equivalent_cycles.toLocaleString(state.lang) + ' → '
        + trend.to_equivalent_cycles.toLocaleString(state.lang);
      node.textContent = t('decline') + ' ' + trend.change_pct_points.toLocaleString(state.lang)
        + ' ' + t('points') + ' (' + span + ' ' + unit + ').';
    }
    if (trend.acceleration) node.textContent += ' ' + t('changing_trend');
    if (data.data_quality.excluded_records) node.textContent += ' ' + t('excluded') + ' ' + data.data_quality.excluded_records + '.';
    if (data.data_quality.warnings.includes('check_reference_capacity')) node.textContent += ' ' + t('referenceWarning');
  }

  function renderDataset(data) {
    const info = $('dataset-info');
    info.replaceChildren();
    if (!data.dataset) return;
    addText(info, 'p', data.dataset.id + ' · ' + data.dataset.citation);
    const link = addText(info, 'a', t('publicSource'));
    link.href = data.dataset.source_url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    addText(info, 'p', t('publicLicense'));
  }

  const SVG = 'http://www.w3.org/2000/svg';
  function shape(svg, tag, attrs) {
    const node = document.createElementNS(SVG, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
    svg.append(node);
    return node;
  }

  function legend(items) {
    const list = document.createElement('ul');
    list.className = 'legend';
    items.forEach(([cls, label]) => {
      const item = document.createElement('li');
      addText(item, 'span', '', 'swatch ' + cls).setAttribute('aria-hidden', 'true');
      item.append(label);
      list.append(item);
    });
    return list;
  }

  function chart(data) {
    const container = $('chart');
    container.replaceChildren();
    $('history-table').replaceChildren();
    if (!data.history.length) {
      addText(container, 'p', t('missing'));
      return;
    }
    const threshold = data.service_threshold_pct;
    const compare = $('compare').checked && state.previous
      && state.previous.cycle_axis === data.cycle_axis
      && state.previous.assessment_id !== data.assessment_id;
    const previous = compare ? state.previous.history : [];
    const observedSpan = data.history.at(-1).equivalent_cycles - data.history[0].equivalent_cycles;
    const forecast = forecastShape(data.history, threshold, data.rul, Math.max(observedSpan, 1) * 1.5);
    const scale = makeScale(previous.length ? [data.history, previous] : [data.history], threshold, forecast ? forecast.extraX : 0);
    const point = (cycle, soh) => scale.x(cycle) + ',' + scale.y(soh);

    const svg = document.createElementNS(SVG, 'svg');
    svg.setAttribute('viewBox', '0 0 920 315');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', t('historyTitle'));
    [scale.minY, threshold, scale.maxY].forEach(value => {
      const y = scale.y(value);
      shape(svg, 'line', {x1: PLOT.left, x2: PLOT.right, y1: y, y2: y, class: value === threshold ? 'grid threshold' : 'grid'});
      const label = shape(svg, 'text', {x: 4, y: y + 4, class: 'axis'});
      label.textContent = Math.round(value) + '%';
    });
    if (previous.length) {
      shape(svg, 'polyline', {points: previous.map(r => point(r.equivalent_cycles, r.soh_pct)).join(' '), class: 'series previous'});
    }
    if (forecast) {
      const band = [forecast.start, forecast.lowEdge, forecast.highEdge].map(p => point(p.cycle, p.soh)).join(' ');
      shape(svg, 'polygon', {points: band, class: 'band'});
      shape(svg, 'line', {
        x1: scale.x(forecast.start.cycle), y1: scale.y(forecast.start.soh),
        x2: scale.x(forecast.middle.cycle), y2: scale.y(forecast.middle.soh), class: 'series forecast',
      });
    }
    shape(svg, 'polyline', {points: data.history.map(r => point(r.equivalent_cycles, r.soh_pct)).join(' '), class: 'series measured'});
    if (data.history.length === 1) {
      shape(svg, 'circle', {cx: scale.x(data.history[0].equivalent_cycles), cy: scale.y(data.history[0].soh_pct), r: 5, class: 'dot'});
    }
    const unit = t(data.cycle_axis === 'equivalent_cycles' ? 'cycles' : 'tests');
    const xLabel = shape(svg, 'text', {x: PLOT.left, y: 300, class: 'axis'});
    xLabel.textContent = data.history[0].equivalent_cycles + ' → '
      + (forecast ? Math.round(scale.maxX) : data.history.at(-1).equivalent_cycles) + ' ' + unit;
    container.append(svg);

    const items = [['measured', t('legendMeasured')], ['threshold', t('legendThreshold')]];
    if (forecast) items.push(['forecast', t('legendForecast')], ['band', t('legendUncertainty')]);
    if (previous.length) items.push(['previous', t('legendPrevious')]);
    container.append(legend(items));
    renderTable(data, unit);
  }

  function renderTable(data, unit) {
    const table = document.createElement('table');
    const header = document.createElement('tr');
    addText(header, 'th', unit);
    addText(header, 'th', t('capacityTitle') + ' (%)');
    table.append(header);
    data.history.forEach(record => {
      const row = document.createElement('tr');
      addText(row, 'td', record.equivalent_cycles.toLocaleString(state.lang));
      addText(row, 'td', record.soh_pct.toLocaleString(state.lang));
      table.append(row);
    });
    $('history-table').append(table);
  }

  const EVIDENCE_LABELS = code => ({
    observed_c: t('temperature'),
    limit_c: t(code === 'charge_too_cold' ? 'minTemp' : 'maxTemp'),
    observed_mv: t('spread'),
    limit_mv: t('spreadLimit'),
    soh_pct: t('capacityTitle') + ' %',
    threshold_pct: t('threshold'),
  });

  function advice(data) {
    const node = $('advice');
    node.replaceChildren();
    if (!data.recommendations.length) addText(node, 'p', t('noAdvice'));
    data.recommendations.forEach(item => {
      const text = ADVICE[state.lang][item.code];
      if (!text) return;
      const article = document.createElement('article');
      article.className = item.priority === 'urgent' ? 'advice warning' : 'advice';
      addText(article, 'h4', text[0]);
      addText(article, 'p', text[1]);
      const labels = EVIDENCE_LABELS(item.code);
      const evidence = Object.entries(item.evidence)
        .map(([key, value]) => (labels[key] || '') + (typeof value === 'number' ? ': ' + value : ''))
        .filter(Boolean).join('; ');
      if (evidence) addText(article, 'p', t('source') + ': ' + evidence, 'note');
      addText(article, 'p', t('verify') + ': ' + text[2]);
      if (/^https:\/\//i.test(item.source)) {
        const link = addText(article, 'a', t('source'));
        link.href = item.source;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
      } else {
        const names = {configured_service_threshold: t('threshold'), vehicle_or_battery_manual: t('limitSource')};
        addText(article, 'p', t('source') + ': ' + (names[item.source] || item.source), 'note');
      }
      node.append(article);
    });
  }

  function formatDate(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return new Intl.DateTimeFormat(state.lang, {dateStyle: 'medium', timeStyle: 'short'}).format(date);
  }

  async function showChange(node) {
    try {
      const change = await call('history/' + encodeURIComponent(state.last.battery_id) + '/changes');
      const names = {improved: 'changeImproved', declined: 'changeDeclined', unchanged: 'changeUnchanged'};
      if (!names[change.capacity_direction]) return;
      const points = change.soh_change_points.toLocaleString(state.lang, {signDisplay: 'exceptZero'});
      addText(node, 'p', t('changeLead') + ' ' + t(names[change.capacity_direction]) + ' (' + points + ' ' + t('points') + ').', 'note');
    } catch { /* fewer than two comparable reports: nothing to add */ }
  }

  /* ----- events ----- */

  $('language').addEventListener('change', () => {
    state.lang = $('language').value;
    try { localStorage.setItem('argus.lang', state.lang); } catch { /* ignore */ }
    localize();
  });

  $('battery-form').addEventListener('input', event => {
    if (event.target.id !== 'capacity-file') markStale();
  });

  let useCases = null;
  $('application').addEventListener('change', async () => {
    if (state.datasetId) return;
    try {
      useCases = useCases || (await call('use-cases')).use_cases;
      const preset = useCases[$('application').value];
      if (preset) {
        $('threshold').value = preset.service_threshold_pct;
        $('margin').value = preset.service_margin_pct;
        if (!$('rate').value && preset.cycles_per_month_hint) $('rate').placeholder = String(preset.cycles_per_month_hint);
      }
    } catch { /* presets are a convenience; the form still works without them */ }
  });

  $('compare').addEventListener('change', () => { if (state.last) chart(state.last); });

  $('capacity-file').addEventListener('change', async () => {
    const file = $('capacity-file').files[0];
    if (!file || state.busy) return;
    setBusy(true);
    markStale();
    state.records = [];
    state.origin = 'user_supplied';
    state.scope = 'pack';
    state.axis = 'equivalent_cycles';
    state.datasetId = null;
    try {
      if (file.size > 2000000) throw new Error('large');
      const result = await call('import-csv', await file.text(), 'text/csv');
      state.records = result.records;
      state.origin = result.data_origin || 'user_supplied';
      const prefix = state.origin === 'synthetic' ? t('synthetic') + ' ' : '';
      $('file-status').textContent = prefix + file.name + ' · ' + state.records.length + ' ' + t('measurements');
      $('message').textContent = '';
    } catch {
      $('file-status').textContent = t('noFile');
      message('fileError');
    } finally {
      setBusy(false);
    }
  });

  $('example').addEventListener('click', async () => {
    if (state.busy) return;
    setBusy(true);
    try { await analyzeLoaded(await call('example')); } catch { message('error'); } finally { setBusy(false); }
  });

  $('public-example').addEventListener('click', async () => {
    if (state.busy) return;
    const count = Number($('public-count').value);
    if (!Number.isInteger(count) || count < 8 || count > 2000) { message('error'); return; }
    setBusy(true);
    message('waiting');
    markStale();
    message('waiting');
    try {
      const id = encodeURIComponent($('public-cell').value);
      const dataset = await call('datasets/' + id + '?observations=' + count);
      await analyzeLoaded(dataset.request);
    } catch { message('publicUnavailable'); } finally { setBusy(false); }
  });

  $('battery-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (state.busy) return;
    setBusy(true);
    message('waiting');
    try { await analyze(makePayload()); } catch { message('error'); } finally { setBusy(false); }
  });

  $('save').addEventListener('click', async () => {
    if (!state.payload || !state.last) return;
    setBusy(true);
    try { await call('save', state.payload); message('localSaved'); } catch { message('error'); } finally { setBusy(false); }
  });

  $('export').addEventListener('click', () => {
    if (!state.last) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(state.last, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'battery-assessment.json';
    link.click();
    URL.revokeObjectURL(url);
  });

  $('saved').addEventListener('click', async () => {
    if (!state.last) return;
    try {
      const list = await call('history/' + encodeURIComponent(state.last.battery_id));
      const node = $('saved-list');
      node.replaceChildren();
      if (!list.length) addText(node, 'p', t('savedEmpty'));
      list.forEach(r => addText(node, 'p', formatDate(r.saved_at) + ' · ' + (r.assessment.soh_pct ?? t('missing')) + '% · ' + r.assessment.battery_id));
      if (list.length > 1) await showChange(node);
    } catch { message('error'); }
  });

  localize();
}
