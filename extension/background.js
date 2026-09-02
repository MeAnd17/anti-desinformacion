/**
 * background.js — Service Worker de la extensión AntiDesinformación
 *
 * Responsabilidades:
 *   1. Comunicarse con el backend FastAPI (http://localhost:8000)
 *   2. Registrar y manejar el menú contextual (clic derecho)
 *   3. Mostrar notificaciones nativas del navegador
 *   4. Actuar como puente de mensajes entre content.js y popup.js
 */

const BACKEND_URL = "http://localhost:8000";
const TIMEOUT_MS  = 20000;

// ---------------------------------------------------------------------------
// Comunicación con el backend
// ---------------------------------------------------------------------------

/**
 * Llama a un endpoint del backend FastAPI.
 *
 * @param {string} endpoint  - Ruta del endpoint, ej: "/analyze/url"
 * @param {object} data      - Cuerpo de la petición (JSON)
 * @returns {Promise<object>} - Respuesta del backend o error estandarizado
 */
async function callAnalysisAPI(endpoint, data) {
  const controller = new AbortController();
  const timerId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const response = await fetch(`${BACKEND_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
      signal: controller.signal,
    });

    clearTimeout(timerId);

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      return {
        error: true,
        message: errorBody.detail || `Error ${response.status} del servidor`,
        status: response.status,
      };
    }

    return await response.json();

  } catch (err) {
    clearTimeout(timerId);

    if (err.name === "AbortError") {
      return {
        error: true,
        message: "El servidor tardó demasiado. Verifica que el backend esté corriendo.",
        code: "TIMEOUT",
      };
    }
    return {
      error: true,
      message: "No se pudo conectar al servidor. ¿Está corriendo el backend en localhost:8000?",
      code: "CONNECTION_ERROR",
    };
  }
}

// ---------------------------------------------------------------------------
// Menú contextual
// ---------------------------------------------------------------------------

// Crear el menú contextual al instalar la extensión
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "anti-desinformacion-verificar",
    title: "🔍 Verificar con Tucuy",
    contexts: ["selection", "link"],
  });

  console.log("[Tucuy] Extensión instalada correctamente.");
});

// Manejar clic en el menú contextual
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "anti-desinformacion-verificar") return;

  const selectionText = info.selectionText || "";
  const linkUrl       = info.linkUrl || "";

  // Determinar qué analizar: texto seleccionado, enlace, o ambos
  const payload = {};
  if (selectionText.trim()) payload.text = selectionText.trim();
  if (linkUrl.trim())       payload.url  = linkUrl.trim();

  // Si hay un enlace y el texto seleccionado parece una URL, usarlo como URL también
  const URL_REGEX = /(?:https?:\/\/|www\.)\S+/i;
  if (!linkUrl && selectionText && URL_REGEX.test(selectionText)) {
    payload.url  = selectionText.trim();
    payload.text = undefined;
  }

  if (!payload.text && !payload.url) return;

  // Notificar al content script que estamos procesando
  chrome.tabs.sendMessage(tab.id, {
    type: "SHOW_OVERLAY_LOADING",
  }).catch(() => {}); // el tab puede no tener content script activo

  const result = await callAnalysisAPI("/analyze/full", payload);

  // Enviar resultado al content script para mostrar overlay
  chrome.tabs.sendMessage(tab.id, {
    type: "SHOW_ANALYSIS_RESULT",
    result,
    context: {
      text: payload.text,
      url:  payload.url,
    },
  }).catch(() => {
    // Si no llega al content script, usar notificación nativa
    showNativeNotification(result);
  });
});

// ---------------------------------------------------------------------------
// Puente de mensajes desde content.js y popup.js
// ---------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "ANALYZE_URLS_BATCH") {
    // content.js pide analizar un lote de URLs
    analyzeBatch(message.urls).then(sendResponse);
    return true; // respuesta asíncrona
  }

  if (message.type === "ANALYZE_TEXT") {
    callAnalysisAPI("/analyze/text", { text: message.text }).then(sendResponse);
    return true;
  }

  if (message.type === "ANALYZE_URL") {
    callAnalysisAPI("/analyze/url", { url: message.url }).then(sendResponse);
    return true;
  }

  if (message.type === "ANALYZE_FULL") {
    callAnalysisAPI("/analyze/full", message.data).then(sendResponse);
    return true;
  }
});

// ---------------------------------------------------------------------------
// Análisis de lotes de URLs (para escaneo automático de página)
// ---------------------------------------------------------------------------

/**
 * Analiza un array de URLs en paralelo y retorna un mapa url → resultado.
 *
 * @param {string[]} urls - Lista de URLs a analizar
 * @returns {Promise<object>} - { [url]: result }
 */
async function analyzeBatch(urls) {
  const results = {};

  // Analizar en grupos de 5 para no saturar el backend
  const CHUNK_SIZE = 5;
  for (let i = 0; i < urls.length; i += CHUNK_SIZE) {
    const chunk = urls.slice(i, i + CHUNK_SIZE);
    const promises = chunk.map(async (url) => {
      const result = await callAnalysisAPI("/analyze/url", { url });
      results[url] = result;
    });
    await Promise.all(promises);
  }

  return results;
}

// ---------------------------------------------------------------------------
// Notificaciones nativas (fallback cuando el overlay no está disponible)
// ---------------------------------------------------------------------------

/**
 * Muestra una notificación nativa del navegador con el resultado del análisis.
 */
function showNativeNotification(result) {
  if (!result) return;

  const riskLevel    = result.overall_risk_level || result.risk_level || "bajo";
  const riskEmojis   = { alto: "🔴", medio: "🟡", bajo: "🟢" };
  const riskLabels   = { alto: "RIESGO ALTO", medio: "PRECAUCIÓN", bajo: "SEGURO" };

  const emoji = riskEmojis[riskLevel]  || "⚪";
  const label = riskLabels[riskLevel]  || "DESCONOCIDO";

  const rawMessage = result.formatted_message || "Análisis completado.";
  // Limpiar emojis y acortar para la notificación
  const shortMessage = rawMessage
    .replace(/[🔴🟡🟢⚠️✅⚡👉💡📋📸🔗🖼️]/gu, "")
    .replace(/\*/g, "")
    .slice(0, 120);

  chrome.notifications.create({
    type:    "basic",
    iconUrl: "icons/icon48.png",
    title:   `Tucuy — ${label}`,
    message: shortMessage.trim() || "Análisis completado.",
    priority: riskLevel === "alto" ? 2 : 1,
  });
}
