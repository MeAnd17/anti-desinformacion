/**
 * content.js — Content Script de la extensión AntiDesinformación
 *
 * Responsabilidades:
 *   1. Escanear automáticamente todos los enlaces (<a href>) de la página
 *      y resaltarlos visualmente según su nivel de riesgo
 *   2. Mostrar tooltips de advertencia al pasar el mouse sobre enlaces marcados
 *   3. Mostrar un overlay de resultados cuando el usuario usa el menú contextual
 */

(function () {
  "use strict";

  // Evitar inicialización múltiple si el script se inyecta más de una vez
  if (window.__tucuyLoaded) return;
  window.__tucuyLoaded = true;

  // ---------------------------------------------------------------------------
  // Constantes y estado
  // ---------------------------------------------------------------------------

  const CLASES = {
    alto:  "antidesinf-riesgo-alto",
    medio: "antidesinf-riesgo-medio",
    bajo:  "antidesinf-riesgo-bajo",
  };

  // URLs ya procesadas para evitar re-análisis
  const urlsProcesadas = new Set();

  // Overlay de carga y resultados
  let overlayEl = null;

  // ---------------------------------------------------------------------------
  // Inyección de estilos CSS
  // ---------------------------------------------------------------------------

  function injectStyles() {
    if (document.getElementById("antidesinf-styles")) return;

    const style = document.createElement("style");
    style.id = "antidesinf-styles";
    style.textContent = `
      /* Estilos para enlaces marcados */
      .antidesinf-riesgo-alto {
        outline: 2px solid #e53935 !important;
        background-color: rgba(229, 57, 53, 0.08) !important;
        border-radius: 2px !important;
        position: relative !important;
      }
      .antidesinf-riesgo-medio {
        outline: 2px solid #f9a825 !important;
        background-color: rgba(249, 168, 37, 0.08) !important;
        border-radius: 2px !important;
        position: relative !important;
      }

      /* Icono de advertencia junto al enlace */
      .antidesinf-badge {
        display: inline-block;
        font-size: 11px;
        margin-left: 3px;
        vertical-align: middle;
        cursor: default;
        line-height: 1;
      }

      /* Tooltip de advertencia */
      .antidesinf-tooltip {
        display: none;
        position: fixed;
        z-index: 2147483647;
        background: #1a1a2e;
        color: #ffffff;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 13px;
        line-height: 1.5;
        max-width: 320px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        pointer-events: none;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        border-left: 4px solid #e53935;
      }
      .antidesinf-tooltip.medio {
        border-left-color: #f9a825;
      }
      .antidesinf-tooltip.visible {
        display: block;
      }

      /* Overlay de resultados del menú contextual */
      #antidesinf-overlay {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 2147483647;
        background: #1a1a2e;
        color: #ffffff;
        padding: 18px 22px;
        border-radius: 12px;
        font-size: 14px;
        line-height: 1.6;
        max-width: 380px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        animation: antidesinf-slide-in 0.25s ease-out;
      }
      @keyframes antidesinf-slide-in {
        from { opacity: 0; transform: translateX(20px); }
        to   { opacity: 1; transform: translateX(0); }
      }
      #antidesinf-overlay .antidesinf-overlay-header {
        font-weight: 700;
        font-size: 15px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      #antidesinf-overlay .antidesinf-overlay-body {
        opacity: 0.9;
        font-size: 13px;
      }
      #antidesinf-overlay .antidesinf-overlay-close {
        position: absolute;
        top: 10px;
        right: 14px;
        cursor: pointer;
        font-size: 18px;
        opacity: 0.6;
        background: none;
        border: none;
        color: #fff;
        padding: 0;
        line-height: 1;
      }
      #antidesinf-overlay .antidesinf-overlay-close:hover {
        opacity: 1;
      }
      #antidesinf-overlay.riesgo-alto  { border-left: 5px solid #e53935; }
      #antidesinf-overlay.riesgo-medio { border-left: 5px solid #f9a825; }
      #antidesinf-overlay.riesgo-bajo  { border-left: 5px solid #43a047; }
    `;
    document.head.appendChild(style);
  }

  // ---------------------------------------------------------------------------
  // Escaneo automático de URLs en la página
  // ---------------------------------------------------------------------------

  /**
   * Extrae todos los enlaces válidos de la página que no han sido procesados.
   */
  function collectNewUrls() {
    const anchors = document.querySelectorAll("a[href]");
    const nuevas = [];

    anchors.forEach((a) => {
      const href = a.href;
      if (
        !href ||
        href.startsWith("javascript:") ||
        href.startsWith("mailto:") ||
        href.startsWith("tel:") ||
        href.startsWith("#") ||
        urlsProcesadas.has(href)
      ) return;

      // Solo URLs con dominio real
      try {
        const url = new URL(href);
        if (!["http:", "https:"].includes(url.protocol)) return;
        nuevas.push({ element: a, url: href });
        urlsProcesadas.add(href);
      } catch {
        // URL inválida, ignorar
      }
    });

    return nuevas;
  }

  /**
   * Aplica la clase CSS y el badge de riesgo al elemento <a>.
   */
  function applyRiskStyle(anchorEl, riskLevel, result) {
    if (riskLevel === "bajo") return; // sin cambio visual para enlaces seguros

    const clase = CLASES[riskLevel] || CLASES.medio;
    anchorEl.classList.add(clase);

    // Badge de advertencia
    const badge = document.createElement("span");
    badge.className = "antidesinf-badge";
    badge.textContent = riskLevel === "alto" ? "⚠️" : "🟡";
    badge.title = "AntiDesinformación: enlace sospechoso";
    anchorEl.insertAdjacentElement("afterend", badge);

    // Tooltip
    setupTooltip(anchorEl, badge, riskLevel, result);
  }

  /**
   * Agrega eventos de hover para mostrar/ocultar el tooltip de advertencia.
   */
  function setupTooltip(anchorEl, badgeEl, riskLevel, result) {
    const tooltip = document.createElement("div");
    tooltip.className = `antidesinf-tooltip ${riskLevel}`;

    const closest = result.closest_domain || "";
    const extracted = result.extracted_domain || "";

    let tooltipText = "";
    if (riskLevel === "alto") {
      tooltipText =
        `⚠️ ENLACE PELIGROSO\n` +
        `Este enlace imita al sitio oficial de "${closest}".\n` +
        `Dominio sospechoso: ${extracted}\n` +
        `No ingreses contraseñas ni datos personales.`;
    } else {
      tooltipText =
        `🟡 ENLACE SOSPECHOSO\n` +
        `Se parece a "${closest}" pero no es el sitio real.\n` +
        `Verifica la dirección antes de hacer clic.`;
    }
    tooltip.textContent = tooltipText;
    document.body.appendChild(tooltip);

    function showTooltip(e) {
      tooltip.style.left = `${Math.min(e.clientX + 12, window.innerWidth - 340)}px`;
      tooltip.style.top  = `${Math.max(e.clientY - 60, 8)}px`;
      tooltip.classList.add("visible");
    }
    function hideTooltip() {
      tooltip.classList.remove("visible");
    }

    [anchorEl, badgeEl].forEach((el) => {
      el.addEventListener("mouseenter", showTooltip);
      el.addEventListener("mousemove",  showTooltip);
      el.addEventListener("mouseleave", hideTooltip);
    });
  }

  /**
   * Escanea la página, envía las URLs al background y aplica estilos.
   */
  async function scanPageUrls() {
    const nuevas = collectNewUrls();
    if (nuevas.length === 0) return;

    const urlsToAnalyze = nuevas.map((n) => n.url);

    // Solicitar análisis al background service worker
    let batchResults;
    try {
      batchResults = await chrome.runtime.sendMessage({
        type: "ANALYZE_URLS_BATCH",
        urls: urlsToAnalyze,
      });
    } catch {
      return; // extensión desconectada o contexto inválido
    }

    if (!batchResults) return;

    // Aplicar estilos según resultado
    nuevas.forEach(({ element, url }) => {
      const result = batchResults[url];
      if (!result || result.error) return;

      const riskLevel = result.risk_level || "bajo";
      applyRiskStyle(element, riskLevel, result);
    });
  }

  // ---------------------------------------------------------------------------
  // Overlay de resultados (menú contextual)
  // ---------------------------------------------------------------------------

  /**
   * Muestra un spinner de carga en el overlay.
   */
  function showOverlayLoading() {
    removeOverlay();
    overlayEl = document.createElement("div");
    overlayEl.id = "antidesinf-overlay";
    overlayEl.className = "riesgo-bajo";
    overlayEl.innerHTML = `
      <div class="antidesinf-overlay-header">
        🔍 Tucuy
      </div>
      <div class="antidesinf-overlay-body">
        Analizando el contenido... por favor espera.
      </div>
    `;
    document.body.appendChild(overlayEl);
  }

  /**
   * Muestra el resultado completo del análisis en el overlay.
   */
  function showAnalysisResult(result, context) {
    removeOverlay();

    const riskLevel  = result.overall_risk_level || result.risk_level || "bajo";
    const riskEmojis = { alto: "🔴", medio: "🟡", bajo: "🟢" };
    const riskLabels = { alto: "RIESGO ALTO", medio: "PRECAUCIÓN", bajo: "SEGURO" };

    const emoji = riskEmojis[riskLevel]  || "⚪";
    const label = riskLabels[riskLevel]  || "ANÁLISIS COMPLETADO";

    // Mensaje formateado — limpiar markdown de WhatsApp
    const rawMessage = result.formatted_message || "Análisis completado.";
    const cleanMessage = rawMessage
      .replace(/\*(.*?)\*/g, "<strong>$1</strong>")
      .replace(/_(.*?)_/g,   "<em>$1</em>")
      .replace(/\n/g,         "<br>");

    overlayEl = document.createElement("div");
    overlayEl.id = "antidesinf-overlay";
    overlayEl.className = `riesgo-${riskLevel}`;
    overlayEl.innerHTML = `
      <button class="antidesinf-overlay-close" title="Cerrar">✕</button>
      <div class="antidesinf-overlay-header">
        ${emoji} Tucuy — ${label}
      </div>
      <div class="antidesinf-overlay-body">
        ${cleanMessage}
        ${context?.url ? `<br><br><small style="opacity:0.6">URL analizada: ${context.url.slice(0, 60)}...</small>` : ""}
      </div>
    `;

    document.body.appendChild(overlayEl);

    // Botón de cierre
    overlayEl.querySelector(".antidesinf-overlay-close").addEventListener("click", removeOverlay);

    // Auto-cerrar después de 15 segundos si el riesgo es bajo
    if (riskLevel === "bajo") {
      setTimeout(removeOverlay, 15000);
    }
  }

  function removeOverlay() {
    if (overlayEl) {
      overlayEl.remove();
      overlayEl = null;
    }
  }

  // ---------------------------------------------------------------------------
  // Mensajes desde el background
  // ---------------------------------------------------------------------------

  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === "SHOW_OVERLAY_LOADING") {
      showOverlayLoading();
    }
    if (message.type === "SHOW_ANALYSIS_RESULT") {
      showAnalysisResult(message.result, message.context);
    }
  });

  // ---------------------------------------------------------------------------
  // Observador de mutaciones para páginas dinámicas (SPA)
  // ---------------------------------------------------------------------------

  const mutationObserver = new MutationObserver(() => {
    // Escaneamos sólo si se agregaron nodos al DOM
    clearTimeout(mutationObserver._debounceTimer);
    mutationObserver._debounceTimer = setTimeout(scanPageUrls, 1500);
  });

  // ---------------------------------------------------------------------------
  // Inicialización
  // ---------------------------------------------------------------------------

  function init() {
    injectStyles();

    // Escaneo inicial (diferido para no bloquear el render de la página)
    setTimeout(scanPageUrls, 1000);

    // Observar cambios futuros en el DOM (páginas SPA como Facebook, Twitter)
    mutationObserver.observe(document.body, {
      childList:  true,
      subtree:    true,
    });
  }

  // Arrancar cuando el DOM esté listo
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
