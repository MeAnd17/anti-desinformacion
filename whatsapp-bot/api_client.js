/**
 * api_client.js
 * Cliente HTTP para comunicarse con el backend FastAPI de anti-desinformación.
 *
 * Expone tres funciones principales:
 *   - analyzeText(text)         → llama POST /analyze/text
 *   - analyzeUrl(url)           → llama POST /analyze/url
 *   - analyzeImage(imageBuffer) → llama POST /analyze/image (multipart)
 *   - analyzeFull(data)         → llama POST /analyze/full (orquestador)
 */

const axios = require("axios");
const FormData = require("form-data");

// URL base del backend. Cambiar si se despliega en otro host.
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

// Tiempo máximo de espera por respuesta del backend (ms)
const TIMEOUT_MS = 30000;

// ---------------------------------------------------------------------------
// Cliente base
// ---------------------------------------------------------------------------

const apiClient = axios.create({
  baseURL: BACKEND_URL,
  timeout: TIMEOUT_MS,
  headers: { "Content-Type": "application/json" },
});

/**
 * Maneja errores de red o del backend de forma unificada.
 * Retorna un objeto de error estandarizado en lugar de lanzar excepción.
 */
function handleApiError(error, context) {
  if (error.code === "ECONNREFUSED" || error.code === "ENOTFOUND") {
    return {
      error: true,
      message:
        "❌ No puedo conectarme al servidor ahora mismo. " +
        "Por favor intenta de nuevo en unos minutos.",
      code: "CONNECTION_ERROR",
    };
  }
  if (error.response) {
    const detail = error.response.data?.detail || "Error desconocido";
    return {
      error: true,
      message: `❌ Error al analizar el contenido: ${detail}`,
      code: "API_ERROR",
      status: error.response.status,
    };
  }
  console.error(`[API Client] Error en ${context}:`, error.message);
  return {
    error: true,
    message: "❌ Ocurrió un error inesperado. Por favor intenta de nuevo.",
    code: "UNKNOWN_ERROR",
  };
}

// ---------------------------------------------------------------------------
// Funciones públicas
// ---------------------------------------------------------------------------

/**
 * Analiza un texto en busca de fake news o desinformación.
 *
 * @param {string} text - Texto a analizar
 * @returns {Promise<object>} - Resultado del análisis con formatted_message
 */
async function analyzeText(text) {
  try {
    const response = await apiClient.post("/analyze/text", { text });
    return response.data;
  } catch (error) {
    return handleApiError(error, "analyzeText");
  }
}

/**
 * Analiza una URL para detectar typosquatting.
 *
 * @param {string} url - URL a analizar
 * @returns {Promise<object>} - Resultado del análisis con formatted_message
 */
async function analyzeUrl(url) {
  try {
    const response = await apiClient.post("/analyze/url", { url });
    return response.data;
  } catch (error) {
    return handleApiError(error, "analyzeUrl");
  }
}

/**
 * Analiza una imagen usando OCR + NLP.
 *
 * @param {Buffer} imageBuffer - Buffer de la imagen
 * @param {string} mimeType    - MIME type (e.g. "image/jpeg")
 * @param {string} filename    - Nombre del archivo
 * @returns {Promise<object>} - Resultado del análisis con formatted_message
 */
async function analyzeImage(imageBuffer, mimeType = "image/jpeg", filename = "image.jpg") {
  try {
    const form = new FormData();
    form.append("file", imageBuffer, {
      filename,
      contentType: mimeType,
    });

    const response = await axios.post(`${BACKEND_URL}/analyze/image`, form, {
      headers: form.getHeaders(),
      timeout: TIMEOUT_MS,
    });
    return response.data;
  } catch (error) {
    return handleApiError(error, "analyzeImage");
  }
}

/**
 * Análisis completo: texto + URL opcionales (orquestador).
 *
 * @param {object} data - { text?: string, url?: string, image_base64?: string }
 * @returns {Promise<object>} - Resultado unificado con overall_risk_level
 */
async function analyzeFull(data) {
  try {
    const response = await apiClient.post("/analyze/full", data);
    return response.data;
  } catch (error) {
    return handleApiError(error, "analyzeFull");
  }
}

module.exports = { analyzeText, analyzeUrl, analyzeImage, analyzeFull };
