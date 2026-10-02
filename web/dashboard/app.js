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
    pageTitle: "ARGUS-NEURO · Консоль состояния парка", language: "Язык", fleetCards: "Карточки активов",
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
    pageTitle: "ARGUS-NEURO · Fleet Health Console", language: "Language", fleetCards: "Fleet asset cards",
  },
  zh: {
    subtitle: "基于证据的电力电子诊断 · 船舶与无人系统平台",
    avgHealth: "平均健康指数", assetsMonitored: "受监测资产", activeAnomalies: "活跃异常",
    backendMode: "推理模式", alertsTitle: "异常日志", noAlerts: "尚未记录任何异常",
    footerLine: "ARGUS-NEURO · 诊断演示。用于真实设备前需经过独立验证。",
    health: "健康指数", rul: "剩余寿命 · 合成刻度", tier1: "频谱", tier2: "趋势",
    ok: "正常", anomaly: "异常", connecting: "连接中…", online: "已连接",
    disconnected: "连接中断", demo: "浏览器演示", stale: "数据已过时",
    warming_up: "收集历史数据", ready: "就绪", degraded: "受限模式", invalid_data: "数据错误",
    modelLive: "ML + DL", modelHeuristic: "受限诊断", modelOffline: "示意",
    reconnect: "连接服务器", startDemo: "启动浏览器演示",
    awaiting: "等待数据。演示仅在您选择后启动。",
    serverSimulation: "来源：服务器模拟 · 未接入设备数据",
    browserSimulation: "来源：浏览器演示 · 示意数据，无模型和真实测量",
    lastUpdate: "更新于", secondsAgo: "秒前", noData: "无数据",
    samples: "历史", evidence: "偏差证据", reference: "基准", sigma: "窗口 σ",
    noEvidence: "无偏差证据", passport: "决策档案", modelVersion: "模型版本",
    disagreement: "检测器结论不一致", syntheticRul: "基于合成数据的估计，并非实际运行小时数",
    unavailableRul: "寿命估计不可用", unknown: "未确定",
    missing_sensors: "缺少必需的传感器", non_finite_sensors: "传感器数值无效",
    invalid_timestamp: "测量时间无效", non_monotonic_timestamp: "测量顺序错乱",
    sampling_gap: "时间序列中断", invalid_waveform: "波形无效",
    non_finite_model_output: "模型输出无效", models_unavailable: "模型不可用", insufficient_history: "历史数据不足",
    reference_unavailable: "无健康基准", uncalibrated_rul: "寿命估计未在设备上校准",
    spectral_anomaly: "频谱检测器发现异常", reconstruction_anomaly: "遥测特征异常",
    sensor_reference_deviation: "传感器偏离健康基准",
    detector_disagreement: "频谱检测器与时序检测器结论不一致",
    no_anomaly_detected: "根据现有数据未发现异常",
    pageTitle: "ARGUS-NEURO · 机队健康控制台", language: "语言", fleetCards: "资产卡片",
  },
  hi: {
    subtitle: "साक्ष्य-आधारित पावर इलेक्ट्रॉनिक्स निदान · समुद्री और मानवरहित प्लेटफ़ॉर्म",
    avgHealth: "औसत स्वास्थ्य सूचकांक", assetsMonitored: "निगरानी में परिसंपत्तियाँ", activeAnomalies: "सक्रिय विसंगतियाँ",
    backendMode: "इन्फ़रेंस मोड", alertsTitle: "विसंगति लॉग", noAlerts: "अभी तक कोई विसंगति दर्ज नहीं हुई",
    footerLine: "ARGUS-NEURO · निदान प्रदर्शन। वास्तविक उपकरण पर उपयोग के लिए स्वतंत्र सत्यापन आवश्यक है।",
    health: "स्वास्थ्य सूचकांक", rul: "शेष जीवन · सिंथेटिक पैमाना", tier1: "स्पेक्ट्रम", tier2: "रुझान",
    ok: "सामान्य", anomaly: "विसंगति", connecting: "कनेक्ट हो रहा है…", online: "कनेक्टेड",
    disconnected: "कनेक्शन टूट गया", demo: "ब्राउज़र डेमो", stale: "डेटा पुराना है",
    warming_up: "इतिहास एकत्र हो रहा है", ready: "तैयार", degraded: "सीमित मोड", invalid_data: "डेटा त्रुटि",
    modelLive: "ML + DL", modelHeuristic: "सीमित निदान", modelOffline: "उदाहरण",
    reconnect: "सर्वर से कनेक्ट करें", startDemo: "ब्राउज़र डेमो शुरू करें",
    awaiting: "डेटा की प्रतीक्षा। डेमो केवल आपके चुनने पर शुरू होता है।",
    serverSimulation: "स्रोत: सर्वर सिमुलेशन · उपकरण डेटा कनेक्ट नहीं है",
    browserSimulation: "स्रोत: ब्राउज़र डेमो · मॉडल और वास्तविक माप के बिना उदाहरण",
    lastUpdate: "अपडेट", secondsAgo: "सेकंड पहले", noData: "कोई डेटा नहीं",
    samples: "इतिहास", evidence: "विचलन के साक्ष्य", reference: "संदर्भ", sigma: "विंडो σ",
    noEvidence: "विचलन का कोई साक्ष्य नहीं", passport: "निर्णय पासपोर्ट", modelVersion: "मॉडल संस्करण",
    disagreement: "डिटेक्टर असहमत हैं", syntheticRul: "सिंथेटिक अनुमान; वास्तविक परिचालन घंटे नहीं",
    unavailableRul: "जीवन अनुमान उपलब्ध नहीं", unknown: "अज्ञात",
    missing_sensors: "आवश्यक सेंसर अनुपस्थित हैं", non_finite_sensors: "सेंसर मान अमान्य हैं",
    invalid_timestamp: "माप का समय अमान्य है", non_monotonic_timestamp: "माप क्रम से बाहर हैं",
    sampling_gap: "माप इतिहास में अंतराल", invalid_waveform: "अमान्य तरंगरूप",
    non_finite_model_output: "मॉडल का आउटपुट अमान्य है", models_unavailable: "मॉडल उपलब्ध नहीं", insufficient_history: "अपर्याप्त इतिहास",
    reference_unavailable: "स्वस्थ संदर्भ उपलब्ध नहीं", uncalibrated_rul: "जीवन अनुमान उपकरण पर कैलिब्रेट नहीं है",
    spectral_anomaly: "स्पेक्ट्रल डिटेक्टर ने विसंगति पाई", reconstruction_anomaly: "असामान्य टेलीमेट्री प्रोफ़ाइल",
    sensor_reference_deviation: "सेंसर स्वस्थ संदर्भ से विचलित हैं",
    detector_disagreement: "स्पेक्ट्रल और टेम्पोरल डिटेक्टर असहमत हैं",
    no_anomaly_detected: "उपलब्ध डेटा में कोई विसंगति नहीं मिली",
    pageTitle: "ARGUS-NEURO · फ़्लीट स्वास्थ्य कंसोल", language: "भाषा", fleetCards: "परिसंपत्ति कार्ड",
  },
  es: {
    subtitle: "Diagnóstico basado en evidencias para electrónica de potencia · plataformas marinas y no tripuladas",
    avgHealth: "Índice de salud medio", assetsMonitored: "Activos monitorizados", activeAnomalies: "Anomalías activas",
    backendMode: "Modo de inferencia", alertsTitle: "Registro de anomalías", noAlerts: "Aún no se han registrado anomalías",
    footerLine: "ARGUS-NEURO · Demostración de diagnóstico. Su uso en equipos reales requiere validación independiente.",
    health: "Índice de salud", rul: "Vida restante · escala sintética", tier1: "Espectro", tier2: "Tendencia",
    ok: "normal", anomaly: "anomalía", connecting: "conectando…", online: "conectado",
    disconnected: "desconectado", demo: "demo en el navegador", stale: "datos obsoletos",
    warming_up: "recopilando historial", ready: "listo", degraded: "modo limitado", invalid_data: "datos no válidos",
    modelLive: "ML + DL", modelHeuristic: "diagnóstico limitado", modelOffline: "ilustración",
    reconnect: "Conectar al servidor", startDemo: "Iniciar demo en el navegador",
    awaiting: "Esperando datos. La demo solo se inicia cuando usted lo elige.",
    serverSimulation: "Fuente: simulación del servidor · sin datos de equipos conectados",
    browserSimulation: "Fuente: demo en el navegador · ilustración sin modelos ni mediciones reales",
    lastUpdate: "Actualizado hace", secondsAgo: "s", noData: "sin datos",
    samples: "Historial", evidence: "Evidencias de desviación", reference: "referencia", sigma: "σ de ventana",
    noEvidence: "Sin evidencias de desviación", passport: "Pasaporte de decisión", modelVersion: "Versión del modelo",
    disagreement: "Los detectores discrepan", syntheticRul: "Estimación sintética; no son horas de operación",
    unavailableRul: "Estimación de vida no disponible", unknown: "desconocido",
    missing_sensors: "Faltan sensores obligatorios", non_finite_sensors: "Valores de sensor no válidos",
    invalid_timestamp: "Marca de tiempo no válida", non_monotonic_timestamp: "Mediciones fuera de orden",
    sampling_gap: "Hueco en el historial de mediciones", invalid_waveform: "Forma de onda no válida",
    non_finite_model_output: "Salida del modelo no válida", models_unavailable: "Modelos no disponibles", insufficient_history: "Historial insuficiente",
    reference_unavailable: "Sin referencia sana", uncalibrated_rul: "La estimación de vida no está calibrada en equipos",
    spectral_anomaly: "El detector espectral identificó una anomalía", reconstruction_anomaly: "Perfil de telemetría atípico",
    sensor_reference_deviation: "Los sensores se desvían de la referencia sana",
    detector_disagreement: "Los detectores espectral y temporal discrepan",
    no_anomaly_detected: "No se identificó ninguna anomalía en los datos disponibles",
    pageTitle: "ARGUS-NEURO · Consola de salud de la flota", language: "Idioma", fleetCards: "Tarjetas de activos",
  },
  fr: {
    subtitle: "Diagnostic fondé sur des preuves pour l’électronique de puissance · plateformes marines et sans équipage",
    avgHealth: "Indice de santé moyen", assetsMonitored: "Actifs surveillés", activeAnomalies: "Anomalies actives",
    backendMode: "Mode d’inférence", alertsTitle: "Journal des anomalies", noAlerts: "Aucune anomalie enregistrée pour l’instant",
    footerLine: "ARGUS-NEURO · Démonstration de diagnostic. Le déploiement sur un équipement réel exige une validation indépendante.",
    health: "Indice de santé", rul: "Durée de vie restante · échelle synthétique", tier1: "Spectre", tier2: "Tendance",
    ok: "normal", anomaly: "anomalie", connecting: "connexion…", online: "connecté",
    disconnected: "déconnecté", demo: "démo dans le navigateur", stale: "données obsolètes",
    warming_up: "collecte de l’historique", ready: "prêt", degraded: "mode limité", invalid_data: "données invalides",
    modelLive: "ML + DL", modelHeuristic: "diagnostic limité", modelOffline: "illustration",
    reconnect: "Se connecter au serveur", startDemo: "Lancer la démo dans le navigateur",
    awaiting: "En attente de données. La démo ne démarre que sur votre choix.",
    serverSimulation: "Source : simulation serveur · aucune donnée d’équipement connectée",
    browserSimulation: "Source : démo dans le navigateur · illustration sans modèles ni mesures réelles",
    lastUpdate: "Mis à jour il y a", secondsAgo: "s", noData: "aucune donnée",
    samples: "Historique", evidence: "Preuves d’écart", reference: "référence", sigma: "σ de fenêtre",
    noEvidence: "Aucune preuve d’écart", passport: "Passeport de décision", modelVersion: "Version du modèle",
    disagreement: "Les détecteurs divergent", syntheticRul: "Estimation synthétique ; pas des heures de fonctionnement",
    unavailableRul: "Estimation de durée de vie indisponible", unknown: "inconnu",
    missing_sensors: "Capteurs obligatoires manquants", non_finite_sensors: "Valeurs de capteur invalides",
    invalid_timestamp: "Horodatage de mesure invalide", non_monotonic_timestamp: "Mesures dans le désordre",
    sampling_gap: "Interruption de la série temporelle", invalid_waveform: "Forme d’onde invalide",
    non_finite_model_output: "Sortie du modèle invalide", models_unavailable: "Modèles indisponibles", insufficient_history: "Historique insuffisant",
    reference_unavailable: "Référence saine indisponible", uncalibrated_rul: "Durée de vie non étalonnée sur équipement",
    spectral_anomaly: "Le détecteur spectral a identifié une anomalie", reconstruction_anomaly: "Profil de télémétrie inhabituel",
    sensor_reference_deviation: "Les capteurs s’écartent de la référence saine",
    detector_disagreement: "Les détecteurs spectral et temporel divergent",
    no_anomaly_detected: "Aucune anomalie identifiée dans les données disponibles",
    pageTitle: "ARGUS-NEURO · Console de santé de la flotte", language: "Langue", fleetCards: "Cartes des actifs",
  },
  de: {
    subtitle: "Evidenzbasierte Diagnose für Leistungselektronik · maritime und unbemannte Plattformen",
    avgHealth: "Durchschnittlicher Zustandsindex", assetsMonitored: "Überwachte Anlagen", activeAnomalies: "Aktive Anomalien",
    backendMode: "Inferenzmodus", alertsTitle: "Anomalieprotokoll", noAlerts: "Bisher keine Anomalien erfasst",
    footerLine: "ARGUS-NEURO · Diagnosedemonstration. Der Einsatz an realen Anlagen erfordert eine unabhängige Validierung.",
    health: "Zustandsindex", rul: "Restlebensdauer · synthetische Skala", tier1: "Spektrum", tier2: "Trend",
    ok: "normal", anomaly: "Anomalie", connecting: "Verbindung wird hergestellt…", online: "verbunden",
    disconnected: "Verbindung getrennt", demo: "Browser-Demo", stale: "veraltete Daten",
    warming_up: "Verlauf wird gesammelt", ready: "bereit", degraded: "eingeschränkter Modus", invalid_data: "ungültige Daten",
    modelLive: "ML + DL", modelHeuristic: "eingeschränkte Diagnose", modelOffline: "Illustration",
    reconnect: "Mit Server verbinden", startDemo: "Browser-Demo starten",
    awaiting: "Warten auf Daten. Die Demo startet nur auf Ihre Auswahl.",
    serverSimulation: "Quelle: Serversimulation · keine Anlagendaten verbunden",
    browserSimulation: "Quelle: Browser-Demo · Illustration ohne Modelle und reale Messungen",
    lastUpdate: "Aktualisiert vor", secondsAgo: "s", noData: "keine Daten",
    samples: "Verlauf", evidence: "Abweichungsnachweise", reference: "Referenz", sigma: "Fenster-σ",
    noEvidence: "Keine Abweichungsnachweise", passport: "Entscheidungspass", modelVersion: "Modellversion",
    disagreement: "Detektoren widersprechen sich", syntheticRul: "Synthetische Schätzung; keine Betriebsstunden",
    unavailableRul: "Lebensdauerschätzung nicht verfügbar", unknown: "unbekannt",
    missing_sensors: "Erforderliche Sensoren fehlen", non_finite_sensors: "Ungültige Sensorwerte",
    invalid_timestamp: "Ungültiger Messzeitpunkt", non_monotonic_timestamp: "Messungen in falscher Reihenfolge",
    sampling_gap: "Lücke im Messverlauf", invalid_waveform: "Ungültige Wellenform",
    non_finite_model_output: "Ungültige Modellausgabe", models_unavailable: "Modelle nicht verfügbar", insufficient_history: "Unzureichender Verlauf",
    reference_unavailable: "Keine gesunde Referenz verfügbar", uncalibrated_rul: "Lebensdauerschätzung nicht an Anlagen kalibriert",
    spectral_anomaly: "Spektraldetektor hat eine Anomalie erkannt", reconstruction_anomaly: "Ungewöhnliches Telemetrieprofil",
    sensor_reference_deviation: "Sensoren weichen von der gesunden Referenz ab",
    detector_disagreement: "Spektral- und Zeitreihendetektor widersprechen sich",
    no_anomaly_detected: "In den verfügbaren Daten wurde keine Anomalie erkannt",
    pageTitle: "ARGUS-NEURO · Flottenzustandskonsole", language: "Sprache", fleetCards: "Anlagenkarten",
  },
  it: {
    subtitle: "Diagnostica basata su evidenze per l’elettronica di potenza · piattaforme marine e senza equipaggio",
    avgHealth: "Indice di salute medio", assetsMonitored: "Asset monitorati", activeAnomalies: "Anomalie attive",
    backendMode: "Modalità di inferenza", alertsTitle: "Registro anomalie", noAlerts: "Nessuna anomalia registrata finora",
    footerLine: "ARGUS-NEURO · Dimostrazione diagnostica. L’uso su apparecchiature reali richiede una validazione indipendente.",
    health: "Indice di salute", rul: "Vita residua · scala sintetica", tier1: "Spettro", tier2: "Tendenza",
    ok: "normale", anomaly: "anomalia", connecting: "connessione…", online: "connesso",
    disconnected: "disconnesso", demo: "demo nel browser", stale: "dati obsoleti",
    warming_up: "raccolta storico", ready: "pronto", degraded: "modalità limitata", invalid_data: "dati non validi",
    modelLive: "ML + DL", modelHeuristic: "diagnostica limitata", modelOffline: "illustrazione",
    reconnect: "Connetti al server", startDemo: "Avvia demo nel browser",
    awaiting: "In attesa di dati. La demo si avvia solo su tua scelta.",
    serverSimulation: "Fonte: simulazione server · nessun dato di apparecchiature collegato",
    browserSimulation: "Fonte: demo nel browser · illustrazione senza modelli né misure reali",
    lastUpdate: "Aggiornato", secondsAgo: "s fa", noData: "nessun dato",
    samples: "Storico", evidence: "Evidenze di deviazione", reference: "riferimento", sigma: "σ finestra",
    noEvidence: "Nessuna evidenza di deviazione", passport: "Passaporto della decisione", modelVersion: "Versione del modello",
    disagreement: "I rilevatori sono discordi", syntheticRul: "Stima sintetica; non ore di funzionamento",
    unavailableRul: "Stima della vita non disponibile", unknown: "sconosciuto",
    missing_sensors: "Sensori obbligatori mancanti", non_finite_sensors: "Valori dei sensori non validi",
    invalid_timestamp: "Orario di misura non valido", non_monotonic_timestamp: "Misure fuori sequenza",
    sampling_gap: "Interruzione nella serie temporale", invalid_waveform: "Forma d’onda non valida",
    non_finite_model_output: "Output del modello non valido", models_unavailable: "Modelli non disponibili", insufficient_history: "Storico insufficiente",
    reference_unavailable: "Riferimento sano non disponibile", uncalibrated_rul: "Stima della vita non calibrata su apparecchiature",
    spectral_anomaly: "Il rilevatore spettrale ha individuato un’anomalia", reconstruction_anomaly: "Profilo di telemetria insolito",
    sensor_reference_deviation: "I sensori si discostano dal riferimento sano",
    detector_disagreement: "I rilevatori spettrale e temporale sono discordi",
    no_anomaly_detected: "Nessuna anomalia individuata nei dati disponibili",
    pageTitle: "ARGUS-NEURO · Console di salute della flotta", language: "Lingua", fleetCards: "Schede degli asset",
  },
};
// Russian is the primary language; the rest are ordered by number of speakers worldwide.
const LANGUAGES = ["ru", "en", "zh", "hi", "es", "fr", "de", "it"];
const LOCALES = { ru: "ru-RU", en: "en-US", zh: "zh-CN", hi: "hi-IN", es: "es-ES", fr: "fr-FR", de: "de-DE", it: "it-IT" };
const LANG_STORAGE_KEY = "argus.lang";
function loadSavedLang() {
  try { const saved = typeof localStorage === "undefined" ? null : localStorage.getItem(LANG_STORAGE_KEY); return LANGUAGES.includes(saved) ? saved : "ru"; }
  catch (_) { return "ru"; }
}
let currentLang = loadSavedLang();
const t = (key) => I18N[currentLang][key] ?? I18N.ru[key] ?? key;
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
  document.title = t("pageTitle");
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.getAttribute("data-i18n")); });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria"))); });
}
function setLanguage(lang) {
  if (!LANGUAGES.includes(lang)) return;
  currentLang = lang;
  try { if (typeof localStorage !== "undefined") localStorage.setItem(LANG_STORAGE_KEY, lang); } catch (_) { /* Storage may be blocked. */ }
  document.getElementById("langSelect").value = lang;
  applyStaticTranslations();
  render();
}
const langSelect = document.getElementById("langSelect");
langSelect.value = currentLang;
langSelect.addEventListener("change", () => setLanguage(langSelect.value));

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
    const date = new Date(alert.timestamp); timestamp.textContent = Number.isNaN(date.getTime()) ? "—" : date.toLocaleTimeString(LOCALES[currentLang]);
    li.append(message, timestamp); list.appendChild(li);
  }
}
function render() { renderSummary(); renderAlerts(); for (const [id, rec] of state.assets) if (rec.latest) renderCard(id, rec); }
applyStaticTranslations();
connect();
setInterval(() => { renderSummary(); for (const [id, rec] of state.assets) if (rec.latest) renderCard(id, rec); }, 1000);
