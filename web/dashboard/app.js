"use strict";

// Live server snapshots and the opt-in browser demonstration have distinct states.
const I18N = {
  ru: {
    subtitle: "Диагностика с проверяемыми свидетельствами · морские и беспилотные платформы",
    avgHealth: "Средний индекс здоровья", assetsMonitored: "Активов под наблюдением",
    activeAnomalies: "Активные аномалии", backendMode: "Режим инференса",
    alertsTitle: "Журнал аномалий", noAlerts: "Аномалий пока не зафиксировано",
    footerLine: "ARGUS-NEURO · Демонстрация диагностики. Пригодность для реального оборудования требует независимой валидации.",
    health: "Индекс здоровья", rul: "Ресурс · синтетическая шкала", tier1: "Спектр", tier2: "Тренд",
    ok: "норма", anomaly: "аномалия", connecting: "подключение…", online: "подключено",
    disconnected: "связь потеряна", demo: "демо в браузере", stale: "данные устарели",
    warming_up: "сбор истории", ready: "готово", degraded: "ограниченный режим", invalid_data: "ошибка данных",
    modelLive: "ML + DL", modelHeuristic: "ограниченная диагностика", modelOffline: "иллюстрация",
    reconnect: "Подключиться к серверу", startDemo: "Запустить демо в браузере",
    awaiting: "Ожидание данных. Демо запускается только по вашей команде.",
    serverSimulation: "Источник: серверная симуляция · данные оборудования не подключены",
    browserSimulation: "Источник: демо в браузере · иллюстрация, без моделей и реальных измерений",
    lastUpdate: "Обновлено", secondsAgo: "с назад", noData: "нет данных",
    samples: "История", evidence: "Свидетельства отклонения", reference: "эталон", sigma: "σ окна",
    noEvidence: "Нет свидетельств отклонения", passport: "Паспорт решения", modelVersion: "Версия модели",
    disagreement: "Детекторы расходятся", syntheticRul: "Оценка на синтетике; не срок эксплуатации в часах",
    unavailableRul: "Прогноз ресурса недоступен", unknown: "не определено",
    missing_sensors: "Отсутствуют обязательные датчики", non_finite_sensors: "Некорректные значения датчиков",
    invalid_timestamp: "Некорректное время измерения", non_monotonic_timestamp: "Нарушен порядок измерений",
    sampling_gap: "Разрыв временного ряда", invalid_waveform: "Некорректная форма сигнала",
    non_finite_model_output: "Модель вернула некорректный результат", models_unavailable: "Модели недоступны", insufficient_history: "Недостаточно истории",
    reference_unavailable: "Нет здорового эталона", uncalibrated_rul: "Ресурс не откалиброван на оборудовании",
    spectral_anomaly: "Спектральный детектор выявил аномалию", reconstruction_anomaly: "Нетипичный профиль телеметрии",
    sensor_reference_deviation: "Отклонение датчиков от здорового эталона",
    detector_disagreement: "Выводы спектрального и временного детекторов различаются",
    no_anomaly_detected: "По доступным данным аномалия не выявлена",
  },
  en: {
    subtitle: "Evidence-driven diagnostics for marine and unmanned-system power electronics",
    avgHealth: "Average health index", assetsMonitored: "Assets monitored", activeAnomalies: "Active anomalies",
    backendMode: "Inference mode", alertsTitle: "Anomaly log", noAlerts: "No anomalies recorded yet",
    footerLine: "ARGUS-NEURO · Diagnostic demonstration. Deployment on real equipment requires independent validation.",
    health: "Health index", rul: "Life remaining · synthetic scale", tier1: "Spectrum", tier2: "Trend",
    ok: "nominal", anomaly: "anomaly", connecting: "connecting…", online: "connected",
    disconnected: "disconnected", demo: "browser demo", stale: "stale data",
    warming_up: "warming up", ready: "ready", degraded: "limited mode", invalid_data: "invalid data",
    modelLive: "ML + DL", modelHeuristic: "limited diagnostics", modelOffline: "illustration",
    reconnect: "Connect to server", startDemo: "Start browser demo",
    awaiting: "Waiting for data. The demo starts only when you choose it.",
    serverSimulation: "Source: server simulation · equipment data is not connected",
    browserSimulation: "Source: browser demo · illustration without models or real measurements",
    lastUpdate: "Updated", secondsAgo: "s ago", noData: "no data",
    samples: "History", evidence: "Deviation evidence", reference: "reference", sigma: "window σ",
    noEvidence: "No deviation evidence", passport: "Decision passport", modelVersion: "Model version",
    disagreement: "Detectors disagree", syntheticRul: "Synthetic estimate; not operating hours",
    unavailableRul: "Life estimate unavailable", unknown: "unknown",
    missing_sensors: "Required sensors are missing", non_finite_sensors: "Non-finite sensor values",
    invalid_timestamp: "Invalid measurement timestamp", non_monotonic_timestamp: "Measurements are out of order",
    sampling_gap: "Gap in measurement history", invalid_waveform: "Invalid waveform",
    non_finite_model_output: "Invalid model output", models_unavailable: "Models unavailable", insufficient_history: "Insufficient history",
    reference_unavailable: "Healthy reference unavailable", uncalibrated_rul: "Life estimate is not calibrated on equipment",
    spectral_anomaly: "Spectral detector identified an anomaly", reconstruction_anomaly: "Unusual telemetry profile",
    sensor_reference_deviation: "Sensors deviate from the healthy reference",
    detector_disagreement: "Spectral and temporal detectors disagree",
    no_anomaly_detected: "No anomaly identified in the available data",
  },
};
let currentLang = "ru";
const t = (key) => I18N[currentLang][key] || key;
const finite = (value) => typeof value === "number" && Number.isFinite(value);
const number = (value, digits = 0) => finite(value) ? value.toFixed(digits) : "—";
const HISTORY_LEN = 60;
const STALE_AFTER_MS = 10000;
const TREND_SENSOR_BY_TYPE = { MARINE_CONVERTER: "vibration_g", UAV_PDU: "temperature_c" };
const SENSOR_UNITS = { vibration_g: "g", temperature_c: "°C", voltage_v: "V", current_a: "A", frequency_hz: "Hz", load_factor: "" };
const state = { assets: new Map(), cards: new Map(), alerts: [], modelBacked: false, mode: "connecting", source: null, lastReceived: null };
let socket = null;
let reconnectTimer = null;
let connectTimer = null;
let reconnectDelay = 1000;
let offlineTimer = null;
let offlineStep = 0;

function applyStaticTranslations() {
  document.documentElement.lang = currentLang;
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.getAttribute("data-i18n")); });
}
document.querySelectorAll(".lang-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    currentLang = btn.dataset.lang;
    document.querySelectorAll(".lang-btn").forEach((b) => b.classList.toggle("active", b === btn));
    applyStaticTranslations();
    render();
  });
});

function ingestTick(tick) {
  if (!tick || tick.type !== "tick" || !Array.isArray(tick.assets)) return;
  // Reject malformed snapshots before modifying the last known good state.
  if (tick.assets.some((entry) => !entry || typeof entry.asset_id !== "string" || !entry.sensors || !entry.assessment)) return;
  const present = new Set(tick.assets.map((entry) => entry.asset_id));
  for (const id of state.assets.keys()) {
    if (!present.has(id)) { state.assets.delete(id); state.cards.get(id)?.remove(); state.cards.delete(id); }
  }
  for (const entry of tick.assets) {
    let rec = state.assets.get(entry.asset_id);
    if (!rec) { rec = { asset_type: entry.asset_type, sensorHistory: {}, latest: null }; state.assets.set(entry.asset_id, rec); }
    rec.asset_type = entry.asset_type;
    rec.latest = entry;
    const key = TREND_SENSOR_BY_TYPE[entry.asset_type] || Object.keys(entry.sensors)[0];
    const history = rec.sensorHistory[key] || (rec.sensorHistory[key] = []);
    history.push(finite(entry.sensors[key]) ? entry.sensors[key] : null);
    if (history.length > HISTORY_LEN) history.shift();
  }
  state.alerts = Array.isArray(tick.alerts) ? tick.alerts : [];
  state.modelBacked = tick.model_backed === true;
  state.source = tick.source || "unknown";
  state.lastReceived = Date.now();
  render();
}

function clearFeed() {
  state.assets.clear(); state.cards.clear(); state.alerts = []; state.lastReceived = null; state.source = null;
  document.getElementById("fleetGrid").replaceChildren();
}
function isStale() { return state.mode !== "demo" && (state.mode !== "online" || state.lastReceived === null || Date.now() - state.lastReceived > STALE_AFTER_MS); }
function scheduleReconnect() {
  if (reconnectTimer || state.mode === "demo") return;
  reconnectTimer = setTimeout(() => { reconnectTimer = null; connect(); }, reconnectDelay);
  reconnectDelay = Math.min(30000, reconnectDelay * 2);
}
function connect() {
  clearTimeout(connectTimer);
  if (location.protocol === "file:") { state.mode = "disconnected"; render(); return; }
  state.mode = "connecting";
  render();
  let ws;
  try { ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/telemetry`); }
  catch (_) { state.mode = "disconnected"; render(); scheduleReconnect(); return; }
  socket = ws;
  connectTimer = setTimeout(() => { if (socket === ws && ws.readyState !== WebSocket.OPEN) ws.close(); }, 5000);
  ws.addEventListener("open", () => {
    if (socket !== ws) return;
    clearTimeout(connectTimer); reconnectDelay = 1000; state.mode = "online"; render();
  });
  ws.addEventListener("message", (event) => {
    if (socket !== ws) return;
    try { ingestTick(JSON.parse(event.data)); } catch (_) { /* Keep the last valid snapshot. */ }
  });
  ws.addEventListener("close", () => {
    if (socket !== ws) return;
    clearTimeout(connectTimer); socket = null; state.mode = "disconnected"; render(); scheduleReconnect();
  });
  ws.addEventListener("error", () => { /* close or connection timeout schedules retry */ });
}
function disconnectSocket() {
  clearTimeout(reconnectTimer); clearTimeout(connectTimer); reconnectTimer = null;
  const old = socket; socket = null; if (old) old.close();
}
document.getElementById("reconnectBtn").addEventListener("click", () => {
  const wasDemo = state.mode === "demo";
  clearInterval(offlineTimer); offlineTimer = null; disconnectSocket();
  if (wasDemo) clearFeed();
  connect();
});
document.getElementById("demoBtn").addEventListener("click", startOfflineSimulation);

const OFFLINE_FLEET = [
  { id: "DEMO-SHIP-01", type: "MARINE_CONVERTER", drift: 0 },
  { id: "DEMO-SHIP-02", type: "MARINE_CONVERTER", drift: 0.35 },
  { id: "DEMO-UAV-01", type: "UAV_PDU", drift: 0.25 },
];
function startOfflineSimulation() {
  if (offlineTimer) return;
  disconnectSocket(); clearFeed(); offlineStep = 0; state.mode = "demo";
  offlineTimer = setInterval(offlineTick, 1500); offlineTick();
}
function offlineTick() {
  offlineStep += 1;
  const assets = OFFLINE_FLEET.map(({ id, type, drift }) => {
    const ramp = Math.min(1, offlineStep * drift / 40);
    const noise = () => (Math.random() - 0.5) * 2;
    const sensors = type === "MARINE_CONVERTER"
      ? { voltage_v: 400 + noise(), current_a: 120, temperature_c: 55, vibration_g: 0.15 + ramp * 0.9, frequency_hz: 50, load_factor: 0.65 }
      : { voltage_v: 48, current_a: 35, temperature_c: 42 + ramp * 38, vibration_g: 0.35, frequency_hz: 400, load_factor: 0.55 };
    return { asset_id: id, asset_type: type, sensors, assessment: {
      health_index: 100 * (1 - ramp), baseline_anomaly_score: ramp, autoencoder_anomaly_score: null,
      is_anomaly: ramp > 0.45, rul_normalized: null, rul_hours: null, status: "degraded", rul_basis: "unavailable",
      data_quality: { issues: ["models_unavailable"], samples_collected: offlineStep, samples_required: 24 },
      evidence: [], explanation: [], model_backed: false, source: "browser_demo",
    } };
  });
  ingestTick({ type: "tick", timestamp: new Date().toISOString(), source: "browser_demo", model_backed: false, assets, alerts: [] });
}

function getCss(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function healthColor(value) { return getCss(!finite(value) ? "--text-dim" : value >= 70 ? "--good" : value >= 40 ? "--warn" : "--bad"); }
function drawGauge(canvas, value) {
  const dpr = window.devicePixelRatio || 1, size = 64;
  canvas.width = size * dpr; canvas.height = size * dpr;
  canvas.style.width = `${size}px`; canvas.style.height = `${size}px`;
  const ctx = canvas.getContext("2d"); if (!ctx) return;
  ctx.scale(dpr, dpr); ctx.clearRect(0, 0, size, size);
  ctx.beginPath(); ctx.arc(32, 32, 26, 0, Math.PI * 2); ctx.strokeStyle = "rgba(255,255,255,0.08)"; ctx.lineWidth = 6; ctx.stroke();
  if (!finite(value)) return;
  ctx.beginPath(); ctx.arc(32, 32, 26, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.max(0, Math.min(100, value)) / 100);
  ctx.strokeStyle = healthColor(value); ctx.lineCap = "round"; ctx.stroke();
}
function drawSparkline(canvas, series, color) {
  const dpr = window.devicePixelRatio || 1, width = canvas.clientWidth || 240, height = 42;
  canvas.width = width * dpr; canvas.height = height * dpr;
  const ctx = canvas.getContext("2d"); if (!ctx) return;
  ctx.scale(dpr, dpr); ctx.clearRect(0, 0, width, height);
  const valid = series.filter(finite); if (valid.length < 2) return;
  const min = Math.min(...valid), span = Math.max(...valid) - min || 1;
  let segment = false;
  ctx.beginPath();
  series.forEach((value, i) => {
    if (!finite(value)) { segment = false; return; }
    const x = (HISTORY_LEN - series.length + i) * width / (HISTORY_LEN - 1);
    const y = height - 4 - (value - min) / span * (height - 8);
    if (segment) ctx.lineTo(x, y); else ctx.moveTo(x, y); segment = true;
  });
  ctx.strokeStyle = color; ctx.lineWidth = 1.6; ctx.stroke();
}
function ensureCard(id) {
  let card = state.cards.get(id); if (card) return card;
  card = document.createElement("article"); card.className = "asset-card";
  // This template is constant. All server-provided strings use textContent.
  card.innerHTML = `
    <div class="asset-card-head"><div><div class="asset-id"></div><div class="asset-type"></div></div><span class="badge status-badge"></span></div>
    <div class="gauge-row"><div class="gauge"><canvas class="gauge-canvas"></canvas></div><div class="gauge-readout"><span class="gauge-value"></span><span class="gauge-caption" data-i18n="health"></span></div></div>
    <div class="sparkline-block"><div class="sparkline-label"><span class="spark-name"></span><b class="spark-value"></b></div><canvas class="sparkline"></canvas></div>
    <div class="metrics-row"><span><span data-i18n="tier1"></span>: <b class="m-tier1"></b></span><span><span data-i18n="tier2"></span>: <b class="m-tier2"></b></span></div>
    <div class="metrics-row"><span><span data-i18n="rul"></span>: <b class="m-rul"></b></span></div>
    <p class="rul-note"></p><div class="quality-line"></div><ul class="quality-issues"></ul>
    <div class="disagreement"></div><details class="evidence-panel" open><summary data-i18n="evidence"></summary><ul class="evidence-list"></ul><ul class="explanation-list"></ul></details>
    <details class="decision-passport"><summary data-i18n="passport"></summary><div class="passport-id"></div><div class="model-version"></div></details>`;
  card.querySelector(".asset-id").textContent = id;
  card.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.getAttribute("data-i18n")); });
  state.cards.set(id, card); document.getElementById("fleetGrid").appendChild(card); return card;
}
function fillList(list, values) {
  list.replaceChildren();
  for (const value of values) { const li = document.createElement("li"); li.textContent = value; list.appendChild(li); }
}
function renderCard(id, rec) {
  const card = ensureCard(id), a = rec.latest.assessment, stale = isStale();
  const anomaly = a.is_anomaly === true;
  const status = stale ? "stale" : anomaly ? "anomaly" : a.status === "ready" ? "ok" : a.status || "unknown";
  card.classList.toggle("anomaly", anomaly); card.classList.toggle("stale", stale);
  const badge = card.querySelector(".status-badge"); badge.textContent = t(status);
  badge.className = `badge status-badge ${stale ? "unknown" : anomaly ? "anomaly" : status === "ok" ? "ok" : "unknown"}`;
  card.querySelector(".asset-type").textContent = rec.asset_type;
  drawGauge(card.querySelector(".gauge-canvas"), a.health_index);
  card.querySelector(".gauge-value").textContent = number(a.health_index);
  const key = TREND_SENSOR_BY_TYPE[rec.asset_type] || Object.keys(rec.sensorHistory)[0];
  const series = rec.sensorHistory[key] || [], last = series[series.length - 1];
  card.querySelector(".spark-name").textContent = key || "—";
  card.querySelector(".spark-value").textContent = `${number(last, 2)} ${SENSOR_UNITS[key] || ""}`;
  drawSparkline(card.querySelector(".sparkline"), series, healthColor(a.health_index));
  card.querySelector(".m-tier1").textContent = number(a.baseline_anomaly_score, 2);
  card.querySelector(".m-tier2").textContent = number(a.autoencoder_anomaly_score, 2);
  card.querySelector(".m-rul").textContent = a.rul_basis === "synthetic" && finite(a.rul_normalized) ? `${number(a.rul_normalized * 100)}%` : "—";
  card.querySelector(".rul-note").textContent = t(a.rul_basis === "synthetic" ? "syntheticRul" : "unavailableRul");
  const quality = a.data_quality || {};
  card.querySelector(".quality-line").textContent = `${t("samples")}: ${number(quality.samples_collected)} / ${number(quality.samples_required)}`;
  fillList(card.querySelector(".quality-issues"), (quality.issues || []).map(t));
  const disagreement = card.querySelector(".disagreement");
  disagreement.textContent = a.detector_disagreement ? t("disagreement") : "";
  const evidence = Array.isArray(a.evidence) ? a.evidence : [];
  fillList(card.querySelector(".evidence-list"), evidence.length ? evidence.map((e) => `${e.sensor}: ${number(e.observed, 2)} ${SENSOR_UNITS[e.sensor] || ""} · ${t("reference")} ${number(e.reference, 2)} · ${t("sigma")} ${number(e.deviation_sigma, 1)}`) : [t("noEvidence")]);
  fillList(card.querySelector(".explanation-list"), (a.explanation || []).map(t));
  card.querySelector(".passport-id").textContent = a.assessment_id || "—";
  card.querySelector(".model-version").textContent = `${t("modelVersion")}: ${a.model_version || "—"}`;
}
function renderSummary() {
  const records = [...state.assets.values()].filter((r) => r.latest);
  const healthyValues = records.map((r) => r.latest.assessment.health_index).filter(finite);
  const average = healthyValues.length ? healthyValues.reduce((a, b) => a + b, 0) / healthyValues.length : null;
  const summary = document.getElementById("summaryAvgHealth"); summary.textContent = number(average); summary.style.color = healthColor(average);
  document.getElementById("summaryAssetCount").textContent = records.length || "—";
  const known = records.filter((r) => typeof r.latest.assessment.is_anomaly === "boolean");
  document.getElementById("summaryAnomalyCount").textContent = known.length ? `${known.filter((r) => r.latest.assessment.is_anomaly).length} / ${known.length}` : "—";
  document.getElementById("summaryBackend").textContent = !records.length ? "—" : t(state.mode === "demo" ? "modelOffline" : state.modelBacked ? "modelLive" : "modelHeuristic");
  const stale = isStale();
  const mode = state.mode === "online" && stale ? "stale" : state.mode;
  document.getElementById("connLabel").textContent = t(mode);
  document.getElementById("connDot").className = `dot ${mode === "online" ? "online" : mode === "connecting" ? "connecting" : "offline"}`;
  document.getElementById("sourceLabel").textContent = t(state.source === "browser_demo" ? "browserSimulation" : state.source === "simulation" ? "serverSimulation" : "awaiting");
  const age = state.lastReceived === null ? null : Math.floor((Date.now() - state.lastReceived) / 1000);
  document.getElementById("freshnessLabel").textContent = age === null ? t("noData") : `${stale ? t("stale") + " · " : ""}${t("lastUpdate")} ${age} ${t("secondsAgo")}`;
  document.getElementById("sourceBanner").classList.toggle("stale", stale);
  document.getElementById("demoBtn").disabled = state.mode === "demo";
}
function renderAlerts() {
  const list = document.getElementById("alertsList"); list.replaceChildren();
  if (!state.alerts.length) { const li = document.createElement("li"); li.className = "alert-empty"; li.textContent = t("noAlerts"); list.appendChild(li); return; }
  for (const alert of state.alerts) {
    const li = document.createElement("li"), message = document.createElement("span"), timestamp = document.createElement("span");
    message.textContent = alert.asset_id ? `${t("anomaly")}: ${alert.asset_id}` : String(alert.message || "");
    timestamp.className = "ts";
    const date = new Date(alert.timestamp); timestamp.textContent = Number.isNaN(date.getTime()) ? "—" : date.toLocaleTimeString(currentLang === "ru" ? "ru-RU" : "en-US");
    li.append(message, timestamp); list.appendChild(li);
  }
}
function render() { renderSummary(); renderAlerts(); for (const [id, rec] of state.assets) if (rec.latest) renderCard(id, rec); }
applyStaticTranslations();
connect();
setInterval(() => { renderSummary(); for (const [id, rec] of state.assets) if (rec.latest) renderCard(id, rec); }, 1000);
