"use strict";

/**
 * ARGUS-NEURO dashboard client.
 *
 * Connects to the FastAPI WebSocket feed (/ws/telemetry) and renders the
 * live two-tier health assessment for every asset in the fleet. If no
 * backend is reachable (e.g. the page was opened as a static file), it
 * falls back to a self-contained client-side simulation so the console
 * is still a meaningful demo on its own.
 */

// ---------------------------------------------------------------------
// i18n
// ---------------------------------------------------------------------
const I18N = {
  ru: {
    subtitle: "Прогнозная диагностика силовой электроники · морские и беспилотные платформы",
    avgHealth: "Средний индекс здоровья",
    assetsMonitored: "Активов под наблюдением",
    activeAnomalies: "Активные аномалии",
    backendMode: "Режим инференса",
    alertsTitle: "Журнал аномалий",
    noAlerts: "Аномалий пока не зафиксировано",
    footerLine: "ARGUS-NEURO — платформа прогнозной диагностики и мониторинга состояния силовой электроники (C++/Python, ML + DL)",
    health: "Индекс здоровья",
    rul: "Остаточный ресурс",
    hours: "ч",
    tier1: "Tier-1 (спектр)",
    tier2: "Tier-2 (тренд, DL)",
    ok: "норма",
    anomaly: "аномалия",
    connecting: "подключение…",
    online: "подключено",
    offline: "офлайн-демо",
    modelLive: "ML+DL (обучено)",
    modelHeuristic: "эвристика (модели не обучены)",
    modelOffline: "офлайн-симуляция",
  },
  en: {
    subtitle: "Predictive health intelligence for marine and unmanned-system power electronics",
    avgHealth: "Average health index",
    assetsMonitored: "Assets monitored",
    activeAnomalies: "Active anomalies",
    backendMode: "Inference mode",
    alertsTitle: "Anomaly log",
    noAlerts: "No anomalies recorded yet",
    footerLine: "ARGUS-NEURO — predictive maintenance & condition-monitoring platform for power electronics (C++/Python, ML + DL)",
    health: "Health index",
    rul: "Remaining useful life",
    hours: "h",
    tier1: "Tier-1 (spectral)",
    tier2: "Tier-2 (trend, DL)",
    ok: "nominal",
    anomaly: "anomaly",
    connecting: "connecting…",
    online: "live",
    offline: "offline demo",
    modelLive: "ML+DL (trained)",
    modelHeuristic: "heuristic (models untrained)",
    modelOffline: "offline simulation",
  },
};

let currentLang = "ru";
const t = (key) => I18N[currentLang][key] || key;

function applyStaticTranslations() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    el.textContent = t(key);
  });
}

document.querySelectorAll(".lang-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    currentLang = btn.dataset.lang;
    document.querySelectorAll(".lang-btn").forEach((b) => b.classList.toggle("active", b === btn));
    applyStaticTranslations();
    render();
  });
});

// ---------------------------------------------------------------------
// Domain constants
// ---------------------------------------------------------------------
const TREND_SENSOR_BY_TYPE = {
  MARINE_CONVERTER: "vibration_g",
  UAV_PDU: "temperature_c",
};
const SENSOR_UNITS = {
  vibration_g: "g",
  temperature_c: "°C",
  voltage_v: "V",
  current_a: "A",
  frequency_hz: "Hz",
  load_factor: "",
};
const HISTORY_LEN = 60;

// ---------------------------------------------------------------------
// State
// ---------------------------------------------------------------------
const state = {
  assets: new Map(), // asset_id -> { asset_type, sensorHistory: {key:[...]}, healthHistory: [...], latest: {...} }
  alerts: [],
  modelBacked: true,
  mode: "connecting", // connecting | online | offline
};

function ingestTick(tick) {
  for (const entry of tick.assets) {
    let rec = state.assets.get(entry.asset_id);
    if (!rec) {
      rec = { asset_type: entry.asset_type, sensorHistory: {}, healthHistory: [], latest: null };
      state.assets.set(entry.asset_id, rec);
    }
    rec.asset_type = entry.asset_type;
    rec.latest = entry;

    const trendKey = TREND_SENSOR_BY_TYPE[entry.asset_type] || Object.keys(entry.sensors)[0];
    if (!rec.sensorHistory[trendKey]) rec.sensorHistory[trendKey] = [];
    rec.sensorHistory[trendKey].push(entry.sensors[trendKey]);
    if (rec.sensorHistory[trendKey].length > HISTORY_LEN) rec.sensorHistory[trendKey].shift();

    rec.healthHistory.push(entry.assessment.health_index);
    if (rec.healthHistory.length > HISTORY_LEN) rec.healthHistory.shift();
  }
  if (tick.alerts) state.alerts = tick.alerts;
  if (typeof tick.model_backed === "boolean") state.modelBacked = tick.model_backed;
  render();
}

// ---------------------------------------------------------------------
// WebSocket connection with offline fallback
// ---------------------------------------------------------------------
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}/ws/telemetry`;
  let opened = false;

  setConnStatus("connecting");
  let ws;
  try {
    ws = new WebSocket(url);
  } catch (e) {
    startOfflineSimulation();
    return;
  }

  const failTimer = setTimeout(() => {
    if (!opened) {
      ws.close();
      startOfflineSimulation();
    }
  }, 4000);

  ws.addEventListener("open", () => {
    opened = true;
    clearTimeout(failTimer);
    state.mode = "online";
    setConnStatus("online");
  });
  ws.addEventListener("message", (ev) => {
    try {
      ingestTick(JSON.parse(ev.data));
    } catch (e) {
      /* ignore malformed frame */
    }
  });
  ws.addEventListener("close", () => {
    if (state.mode === "online") {
      setConnStatus("offline");
      startOfflineSimulation();
    }
  });
  ws.addEventListener("error", () => {
    /* handled via close/timeout */
  });
}

function setConnStatus(mode) {
  state.mode = mode;
  const dot = document.getElementById("connDot");
  const label = document.getElementById("connLabel");
  dot.className = "dot " + (mode === "online" ? "online" : mode === "connecting" ? "connecting" : "offline");
  label.textContent = mode === "online" ? t("online") : mode === "connecting" ? t("connecting") : t("offline");
}

// ---------------------------------------------------------------------
// Offline client-side simulation (used when no backend is reachable)
// ---------------------------------------------------------------------
const OFFLINE_FLEET = [
  { id: "SHIP-CONV-01", type: "MARINE_CONVERTER", drift: 0.0 },
  { id: "SHIP-CONV-02", type: "MARINE_CONVERTER", drift: 0.15 },
  { id: "SHIP-THRUST-01", type: "MARINE_CONVERTER", drift: 0.35 },
  { id: "UAV-PDU-07", type: "UAV_PDU", drift: 0.0 },
  { id: "UAV-PDU-11", type: "UAV_PDU", drift: 0.25 },
  { id: "UAV-PDU-14", type: "UAV_PDU", drift: 0.1 },
];
let offlineStep = 0;
let offlineTimer = null;

function startOfflineSimulation() {
  if (offlineTimer) return;
  state.mode = "offline";
  setConnStatus("offline");
  offlineTimer = setInterval(offlineTick, 1500);
  offlineTick();
}

function offlineTick() {
  offlineStep += 1;
  const assets = OFFLINE_FLEET.map(({ id, type, drift }) => {
    const ramp = Math.min(1, Math.max(0, (offlineStep * drift) / 40));
    const noise = () => (Math.random() - 0.5) * 2;

    const base = type === "MARINE_CONVERTER"
      ? { voltage_v: 400 + noise(), current_a: 120 + noise() * 2, temperature_c: 55 + noise() * 0.5, vibration_g: 0.15 + ramp * 0.9 + Math.abs(noise()) * 0.02, frequency_hz: 50 + noise() * 0.03, load_factor: 0.65 }
      : { voltage_v: 48 + noise() * 0.3, current_a: 35 + noise(), temperature_c: 42 + ramp * 38 + noise() * 0.5, vibration_g: 0.35 + noise() * 0.02, frequency_hz: 400 + noise() * 0.4, load_factor: 0.55 };

    const baselineScore = Math.min(1, 0.15 + ramp * 0.8 + Math.random() * 0.05);
    const aeScore = Math.min(1, ramp * 0.9);
    const healthIndex = Math.max(0, 100 * (1 - 0.45 * baselineScore - 0.35 * aeScore - 0.2 * ramp));
    const isAnomaly = healthIndex < 55;

    return {
      asset_id: id,
      asset_type: type,
      sensors: base,
      assessment: {
        asset_id: id,
        asset_type: type,
        baseline_anomaly_score: Number(baselineScore.toFixed(3)),
        autoencoder_anomaly_score: Number(aeScore.toFixed(3)),
        is_anomaly: isAnomaly,
        rul_normalized: Number((1 - ramp).toFixed(3)),
        rul_hours: Number(((1 - ramp) * 240).toFixed(1)),
        health_index: Number(healthIndex.toFixed(1)),
        model_backed: false,
      },
    };
  });

  const alerts = [];
  for (const a of assets) {
    if (a.assessment.is_anomaly) {
      alerts.push({
        timestamp: new Date().toISOString(),
        asset_id: a.asset_id,
        message: `${t("anomaly")}: ${a.asset_id} (${t("health")} ${a.assessment.health_index.toFixed(0)})`,
      });
    }
  }

  ingestTick({
    type: "tick",
    timestamp: new Date().toISOString(),
    model_backed: false,
    assets,
    alerts: alerts.slice(0, 10),
  });
}

// ---------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------
function healthColor(value) {
  if (value >= 70) return getCss("--good");
  if (value >= 40) return getCss("--warn");
  return getCss("--bad");
}
function getCss(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function drawGauge(canvas, value) {
  const dpr = window.devicePixelRatio || 1;
  const size = 64;
  canvas.width = size * dpr;
  canvas.height = size * dpr;
  canvas.style.width = size + "px";
  canvas.style.height = size + "px";
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, size, size);

  const cx = size / 2, cy = size / 2, r = size / 2 - 6;
  const start = -Math.PI / 2;
  const end = start + (Math.PI * 2 * Math.min(Math.max(value, 0), 100)) / 100;

  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  ctx.lineWidth = 6;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(cx, cy, r, start, end);
  ctx.strokeStyle = healthColor(value);
  ctx.lineWidth = 6;
  ctx.lineCap = "round";
  ctx.stroke();
}

function drawSparkline(canvas, series, color) {
  const dpr = window.devicePixelRatio || 1;
  const cssWidth = canvas.clientWidth || 240;
  const cssHeight = 42;
  canvas.width = cssWidth * dpr;
  canvas.height = cssHeight * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, cssWidth, cssHeight);
  if (series.length < 2) return;

  const min = Math.min(...series), max = Math.max(...series);
  const span = max - min || 1;
  const stepX = cssWidth / (HISTORY_LEN - 1);
  const offset = HISTORY_LEN - series.length;

  ctx.beginPath();
  series.forEach((v, i) => {
    const x = (offset + i) * stepX;
    const y = cssHeight - 4 - ((v - min) / span) * (cssHeight - 8);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.6;
  ctx.stroke();

  const last = series[series.length - 1];
  const lastX = (offset + series.length - 1) * stepX;
  const lastY = cssHeight - 4 - ((last - min) / span) * (cssHeight - 8);
  ctx.beginPath();
  ctx.arc(lastX, lastY, 2.4, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

const assetTypeIcon = (type) =>
  type === "UAV_PDU"
    ? `<svg viewBox="0 0 24 24"><path d="M12 2 L12 8 M12 16 L12 22 M2 12 L8 12 M16 12 L22 12" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="3.5" stroke-width="2"/></svg>`
    : `<svg viewBox="0 0 24 24"><path d="M3 15 Q7 19 12 15 Q17 11 21 15" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M6 15 L6 6 L15 6 L18 10 L18 15" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

function ensureCard(assetId) {
  let card = document.getElementById(`card-${assetId}`);
  if (card) return card;

  card = document.createElement("article");
  card.className = "asset-card";
  card.id = `card-${assetId}`;
  card.innerHTML = `
    <div class="asset-card-head">
      <div>
        <div class="asset-id">${assetId}</div>
        <div class="asset-type"><span class="type-icon"></span><span class="type-label"></span></div>
      </div>
      <span class="badge ok status-badge">${t("ok")}</span>
    </div>
    <div class="gauge-row">
      <div class="gauge"><canvas class="gauge-canvas"></canvas></div>
      <div class="gauge-readout">
        <span class="gauge-value">--</span>
        <span class="gauge-caption">${t("health")}</span>
      </div>
    </div>
    <div class="sparkline-block">
      <div class="sparkline-label"><span class="spark-name"></span><b class="spark-value">--</b></div>
      <canvas class="sparkline"></canvas>
    </div>
    <div class="metrics-row">
      <span>${t("tier1")}: <b class="m-tier1">--</b></span>
      <span>${t("tier2")}: <b class="m-tier2">--</b></span>
    </div>
    <div class="metrics-row">
      <span>${t("rul")}: <b class="m-rul">--</b> ${t("hours")}</span>
    </div>
  `;
  document.getElementById("fleetGrid").appendChild(card);
  return card;
}

function renderCard(assetId, rec) {
  const card = ensureCard(assetId);
  const a = rec.latest.assessment;
  const isAnomaly = a.is_anomaly;

  card.classList.toggle("anomaly", isAnomaly);
  card.querySelector(".status-badge").textContent = isAnomaly ? t("anomaly") : t("ok");
  card.querySelector(".status-badge").className = "badge status-badge " + (isAnomaly ? "anomaly" : "ok");
  card.querySelector(".type-icon").innerHTML = assetTypeIcon(rec.asset_type);
  card.querySelector(".type-label").textContent = rec.asset_type;

  drawGauge(card.querySelector(".gauge-canvas"), a.health_index);
  card.querySelector(".gauge-value").textContent = a.health_index.toFixed(0);

  const trendKey = TREND_SENSOR_BY_TYPE[rec.asset_type] || Object.keys(rec.sensorHistory)[0];
  const series = rec.sensorHistory[trendKey] || [];
  card.querySelector(".spark-name").textContent = trendKey;
  const lastVal = series[series.length - 1];
  card.querySelector(".spark-value").textContent =
    lastVal !== undefined ? `${lastVal.toFixed(2)} ${SENSOR_UNITS[trendKey] || ""}` : "--";
  drawSparkline(card.querySelector(".sparkline"), series, healthColor(a.health_index));

  card.querySelector(".m-tier1").textContent = a.baseline_anomaly_score.toFixed(2);
  card.querySelector(".m-tier2").textContent = a.autoencoder_anomaly_score.toFixed(2);
  card.querySelector(".m-rul").textContent = a.rul_hours.toFixed(0);
}

function renderSummary() {
  const records = [...state.assets.values()].filter((r) => r.latest);
  const n = records.length;
  const avgHealth = n ? records.reduce((s, r) => s + r.latest.assessment.health_index, 0) / n : 0;
  const anomalies = records.filter((r) => r.latest.assessment.is_anomaly).length;

  document.getElementById("summaryAvgHealth").textContent = n ? avgHealth.toFixed(0) : "--";
  document.getElementById("summaryAvgHealth").style.color = n ? healthColor(avgHealth) : "";
  document.getElementById("summaryAssetCount").textContent = n || "--";
  document.getElementById("summaryAnomalyCount").textContent = anomalies;

  const backendKey = state.mode === "offline" ? "modelOffline" : state.modelBacked ? "modelLive" : "modelHeuristic";
  document.getElementById("summaryBackend").textContent = t(backendKey);
}

function renderAlerts() {
  const list = document.getElementById("alertsList");
  if (!state.alerts.length) {
    list.innerHTML = `<li class="alert-empty">${t("noAlerts")}</li>`;
    return;
  }
  list.innerHTML = state.alerts
    .map((a) => {
      const time = new Date(a.timestamp).toLocaleTimeString(currentLang === "ru" ? "ru-RU" : "en-US");
      return `<li><span>${a.message}</span><span class="ts">${time}</span></li>`;
    })
    .join("");
}

function render() {
  renderSummary();
  renderAlerts();
  for (const [assetId, rec] of state.assets) {
    if (rec.latest) renderCard(assetId, rec);
  }
}

// ---------------------------------------------------------------------
applyStaticTranslations();
connect();
