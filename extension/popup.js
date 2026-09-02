/**
 * popup.js — Lógica del popup de Tucuy
 */

"use strict";

// ---------------------------------------------------------------------------
// Referencias DOM
// ---------------------------------------------------------------------------

const statusDot      = document.getElementById("statusDot");
const statusText     = document.getElementById("statusText");

const inputTexto     = document.getElementById("inputTexto");
const inputUrl       = document.getElementById("inputUrl");
const inputTextoFull = document.getElementById("inputTextoFull");
const inputUrlFull   = document.getElementById("inputUrlFull");

const btnTexto  = document.getElementById("btnTexto");
const btnUrl    = document.getElementById("btnUrl");
const btnFull   = document.getElementById("btnFull");
const btnImagen = document.getElementById("btnImagen");

const dropZone     = document.getElementById("dropZone");
const inputFile    = document.getElementById("inputFile");
const imagePreview = document.getElementById("imagePreview");
const dropLabel    = document.getElementById("dropLabel");

const resultArea      = document.getElementById("resultArea");
const resultCard      = document.getElementById("resultCard");
const resultRiskLabel = document.getElementById("resultRiskLabel");
const resultMessage   = document.getElementById("resultMessage");

// Imagen seleccionada (base64 sin prefijo)
let selectedImageBase64 = null;
let selectedImageMime   = null;

// ---------------------------------------------------------------------------
// Estado del servidor
// ---------------------------------------------------------------------------

async function checkServerStatus() {
  try {
    const response = await fetch("http://localhost:8000/health", {
      method: "GET",
      signal: AbortSignal.timeout(4000),
    });
    if (response.ok) {
      setStatus("online", "Servidor activo ✓");
    } else {
      setStatus("offline", "Error en el servidor");
    }
  } catch {
    setStatus("offline", "Servidor no disponible — inicia el backend");
  }
}

function setStatus(state, text) {
  statusDot.className    = `status-dot ${state}`;
  statusText.textContent = text;
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`panel-${btn.dataset.tab}`).classList.add("active");
    hideResult();
  });
});

// ---------------------------------------------------------------------------
// Zona de imagen — clic y drag & drop
// ---------------------------------------------------------------------------

dropZone.addEventListener("click", () => inputFile.click());

inputFile.addEventListener("change", () => {
  if (inputFile.files[0]) loadImage(inputFile.files[0]);
});

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith("image/")) loadImage(file);
});

function loadImage(file) {
  if (file.size > 5 * 1024 * 1024) {
    showResultError("La imagen supera el límite de 5MB.");
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    const dataUrl = e.target.result;
    // Separar el prefijo "data:image/jpeg;base64," del contenido
    selectedImageBase64 = dataUrl.split(",")[1];
    selectedImageMime   = file.type;

    // Mostrar preview
    imagePreview.src = dataUrl;
    imagePreview.classList.add("visible");

    // Actualizar zona de drop
    dropZone.classList.add("has-image");
    dropLabel.textContent = `✓ ${file.name}`;

    // Habilitar botón
    btnImagen.disabled = false;
  };
  reader.readAsDataURL(file);
}

// ---------------------------------------------------------------------------
// Botones de análisis
// ---------------------------------------------------------------------------

btnTexto.addEventListener("click", async () => {
  const text = inputTexto.value.trim();
  if (!text) { shakeInput(inputTexto); return; }

  setButtonLoading(btnTexto, true);
  showResultLoading();

  const result = await chrome.runtime.sendMessage({ type: "ANALYZE_TEXT", text });

  setButtonLoading(btnTexto, false);
  renderResult(result);
});

btnUrl.addEventListener("click", async () => {
  const url = inputUrl.value.trim();
  if (!url) { shakeInput(inputUrl); return; }

  setButtonLoading(btnUrl, true);
  showResultLoading();

  const result = await chrome.runtime.sendMessage({ type: "ANALYZE_URL", url });

  setButtonLoading(btnUrl, false);
  renderResult(result);
});

btnImagen.addEventListener("click", async () => {
  if (!selectedImageBase64) return;

  setButtonLoading(btnImagen, true);
  showResultLoading();

  // Enviar como análisis full con image_base64
  const result = await chrome.runtime.sendMessage({
    type: "ANALYZE_FULL",
    data: { image_base64: selectedImageBase64 },
  });

  setButtonLoading(btnImagen, false);
  renderResult(result);
});

btnFull.addEventListener("click", async () => {
  const text = inputTextoFull.value.trim();
  const url  = inputUrlFull.value.trim();

  if (!text && !url) {
    shakeInput(inputTextoFull);
    shakeInput(inputUrlFull);
    return;
  }

  setButtonLoading(btnFull, true);
  showResultLoading();

  const data = {};
  if (text) data.text = text;
  if (url)  data.url  = url;

  const result = await chrome.runtime.sendMessage({ type: "ANALYZE_FULL", data });

  setButtonLoading(btnFull, false);
  renderResult(result);
});

// Enter en inputs de una línea
inputUrl.addEventListener("keydown",    (e) => { if (e.key === "Enter") btnUrl.click(); });
inputUrlFull.addEventListener("keydown", (e) => { if (e.key === "Enter") btnFull.click(); });

// ---------------------------------------------------------------------------
// Renderizado de resultados
// ---------------------------------------------------------------------------

function renderResult(result) {
  if (!result) { showResultError("No se recibió respuesta del servidor."); return; }
  if (result.error) { showResultError(result.message || "Error desconocido."); return; }

  const riskLevel  = result.overall_risk_level || result.risk_level || "bajo";
  const riskEmojis = { alto: "🔴", medio: "🟡", bajo: "🟢", incierto: "🔎" };
  const riskLabels = { alto: "RIESGO ALTO", medio: "PRECAUCIÓN", bajo: "SEGURO", incierto: "NO SE PUEDE VERIFICAR" };

  const emoji = riskEmojis[riskLevel] || "⚪";
  const label = riskLabels[riskLevel] || "ANÁLISIS COMPLETADO";

  const rawMsg  = result.formatted_message || "Análisis completado.";
  const htmlMsg = rawMsg
    .replace(/\*(.*?)\*/g, "<strong>$1</strong>")
    .replace(/_(.*?)_/g,   "<em>$1</em>")
    .replace(/\n/g,         "<br>");

  resultRiskLabel.innerHTML = `${emoji} ${label}`;
  resultMessage.innerHTML   = htmlMsg;
  resultCard.className = `result-card riesgo-${riskLevel}`;
  resultArea.classList.add("visible");
}

function showResultLoading() {
  resultRiskLabel.innerHTML = `<span class="spinner"></span> Analizando...`;
  resultMessage.innerHTML   = "Por favor espera un momento.";
  resultCard.className      = "result-card loading";
  resultArea.classList.add("visible");
}

function showResultError(message) {
  resultRiskLabel.innerHTML = "❌ Error";
  resultMessage.textContent = message;
  resultCard.className      = "result-card";
  resultArea.classList.add("visible");
}

function hideResult() {
  resultArea.classList.remove("visible");
}

// ---------------------------------------------------------------------------
// Utilidades de UI
// ---------------------------------------------------------------------------

function setButtonLoading(btn, loading) {
  btn.disabled = loading;
  if (loading) {
    btn.dataset.originalText = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> Analizando...`;
  } else {
    btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
  }
}

function shakeInput(inputEl) {
  inputEl.style.borderColor = "#e53935";
  inputEl.focus();
  setTimeout(() => { inputEl.style.borderColor = ""; }, 1500);
}

// ---------------------------------------------------------------------------
// Inicialización
// ---------------------------------------------------------------------------

checkServerStatus();
