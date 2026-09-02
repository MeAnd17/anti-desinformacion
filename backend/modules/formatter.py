"""
Módulo Formatter — Genera mensajes amigables para usuarios vulnerables.

Traduce resultados técnicos (JSON de análisis) en mensajes con emojis,
lenguaje coloquial y recomendaciones claras para adultos mayores y usuarios
con poca experiencia digital.
"""

from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# Plantillas de mensajes por nivel de riesgo y tipo de análisis
# ---------------------------------------------------------------------------

_TEMPLATES = {
    "whatsapp": {
        "alto": {
            "fake_news": (
                "🔴 *¡CUIDADO!* Este mensaje parece ser una *noticia falsa* "
                "(confianza: {confidence}%).\n\n"
                "❌ La información que contiene puede ser inventada o exagerada "
                "para asustarte o confundirte.\n\n"
                "👉 *No lo compartas.* Antes de creerlo, verifica en fuentes "
                "oficiales como andina.pe o rpp.pe."
            ),
            "typosquatting": (
                "🔴 *¡ENLACE PELIGROSO!* Este enlace imita al sitio oficial de "
                "*{closest_domain}* pero NO es el real.\n\n"
                "⚠️ El dominio sospechoso es: `{extracted_domain}`\n"
                "✅ El dominio real es: `{closest_domain}`\n\n"
                "👉 *No hagas clic* en este enlace. Los estafadores lo usan para "
                "robar tus contraseñas o datos bancarios."
            ),
            "imagen": (
                "🔴 *¡CUIDADO!* La imagen que enviaste contiene texto sospechoso.\n\n"
                "📋 Texto detectado:\n_{extracted_text}_\n\n"
                "👉 *No compartas esta imagen.* Puede ser parte de una cadena de "
                "desinformación o un intento de estafa."
            ),
            "combinado": (
                "🔴 *¡ALERTA DE RIESGO ALTO!*\n\n"
                "Este contenido tiene múltiples señales de peligro:\n"
                "{detalle}\n\n"
                "👉 *No compartas ni hagas clic en nada.* Si crees que es "
                "importante, verifica en los sitios oficiales."
            ),
        },
        "medio": {
            "fake_news": (
                "🟡 *Ten precaución* con este mensaje.\n\n"
                "Tiene algunas características de desinformación, pero no estamos "
                "completamente seguros (confianza: {confidence}%).\n\n"
                "👉 Antes de compartirlo, verifica la información en una fuente "
                "confiable como *andina.pe*, *rpp.pe* o *elcomercio.pe*."
            ),
            "typosquatting": (
                "🟡 *Este enlace es sospechoso.*\n\n"
                "Se parece mucho al sitio oficial de *{closest_domain}*, "
                "pero tiene diferencias en la dirección web.\n\n"
                "⚠️ Enlace recibido: `{extracted_domain}`\n"
                "✅ Sitio real: `{closest_domain}`\n\n"
                "👉 *No ingreses tus datos.* Si necesitas visitar ese sitio, "
                "escribe la dirección directamente en tu navegador."
            ),
            "imagen": (
                "🟡 *Ten cuidado* con esta imagen.\n\n"
                "El texto que contiene tiene algunas señales de alerta.\n\n"
                "👉 Verifica la información antes de compartirla."
            ),
            "combinado": (
                "🟡 *Precaución con este contenido.*\n\n"
                "{detalle}\n\n"
                "👉 Verifica la información antes de actuar o compartirla."
            ),
        },
        "bajo": {
            "fake_news": (
                "🟢 *Este mensaje parece seguro.*\n\n"
                "No encontramos señales claras de desinformación.\n\n"
                "💡 Recuerda: siempre es bueno verificar las noticias importantes "
                "en fuentes oficiales."
            ),
            "typosquatting": (
                "🟢 *Este enlace parece legítimo.*\n\n"
                "No encontramos señales de que sea una imitación de otro sitio.\n\n"
                "💡 Aun así, ten cuidado con lo que ingresas en páginas web."
            ),
            "imagen": (
                "🟢 *Esta imagen parece segura.*\n\n"
                "No encontramos texto sospechoso en ella."
            ),
            "combinado": (
                "🟢 *Este contenido parece seguro.*\n\n"
                "No encontramos señales de peligro.\n\n"
                "💡 Siempre es bueno ser cauteloso en internet."
            ),
        },
    },
    "api": {
        # Para la API y la extensión Chrome, mensajes sin markdown de WhatsApp
        "alto": {
            "fake_news": (
                "⚠️ RIESGO ALTO: Posible noticia falsa detectada (confianza: {confidence}%). "
                "No compartas este contenido sin verificar."
            ),
            "typosquatting": (
                "⚠️ RIESGO ALTO: Enlace sospechoso. Imita a '{closest_domain}' "
                "pero el dominio real es '{extracted_domain}'. No hagas clic."
            ),
            "imagen": (
                "⚠️ RIESGO ALTO: Texto sospechoso detectado en la imagen. "
                "No compartas esta imagen."
            ),
            "combinado": (
                "⚠️ RIESGO ALTO: Múltiples señales de peligro detectadas. "
                "No compartas ni hagas clic en nada."
            ),
        },
        "medio": {
            "fake_news": (
                "⚡ RIESGO MEDIO: Este contenido tiene características de desinformación. "
                "Verifica en fuentes oficiales antes de compartir."
            ),
            "typosquatting": (
                "⚡ RIESGO MEDIO: Enlace sospechoso. Se parece a '{closest_domain}'. "
                "Verifica la dirección web antes de ingresar datos."
            ),
            "imagen": (
                "⚡ RIESGO MEDIO: La imagen contiene texto con señales de alerta. "
                "Verifica antes de compartir."
            ),
            "combinado": (
                "⚡ RIESGO MEDIO: Se encontraron algunas señales de alerta. "
                "Verifica la información antes de actuar."
            ),
        },
        "bajo": {
            "fake_news": "✅ RIESGO BAJO: El contenido parece legítimo.",
            "typosquatting": "✅ RIESGO BAJO: El enlace parece legítimo.",
            "imagen": "✅ RIESGO BAJO: No se encontró contenido sospechoso en la imagen.",
            "combinado": "✅ RIESGO BAJO: El contenido parece seguro.",
        },
    },
}


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


def format_response(analysis_result: dict, channel: str = "whatsapp") -> str:
    """
    Genera un mensaje amigable a partir del resultado del análisis.

    Args:
        analysis_result: dict retornado por cualquiera de los módulos de análisis
                         o por el endpoint /analyze/full.
        channel: "whatsapp" (con markdown de WhatsApp) o "api" (texto plano con emojis).

    Returns:
        Mensaje formateado como string listo para enviar al usuario.
    """
    if channel not in _TEMPLATES:
        channel = "api"

    templates = _TEMPLATES[channel]

    # Determinar el nivel de riesgo general
    risk_level = (
        analysis_result.get("overall_risk_level")
        or analysis_result.get("risk_level")
        or "bajo"
    )

    # Caso especial: imagen con texto insuficiente para verificar
    if risk_level == "incierto":
        texto = ""
        ocr = analysis_result.get("ocr", {})
        if ocr:
            texto = (ocr.get("extracted_text") or "")[:80].strip()

        if channel == "whatsapp":
            return (
                "🔎 *No puedo verificar esta imagen con certeza.*\n\n"
                f"{'Texto encontrado: _' + texto + '_' + chr(10) + chr(10) if texto else ''}"
                "El contenido es demasiado breve o ambiguo para analizarlo con precisión.\n\n"
                "👉 Si sospechas que es falsa, verifica en *andina.pe*, *rpp.pe* o *elcomercio.pe* "
                "antes de compartirla."
            )
        else:
            return (
                "🔎 NO SE PUEDE VERIFICAR: La imagen contiene texto insuficiente para un análisis concluyente. "
                + (f"Texto detectado: '{texto}'. " if texto else "")
                + "Verifica en fuentes oficiales antes de compartir."
            )

    # Determinar el tipo de análisis para elegir la plantilla correcta
    source = analysis_result.get("source", "")

    # --- Análisis de texto / NLP puro ---
    if source == "nlp" or "nlp" in analysis_result and "url_analysis" not in analysis_result:
        nlp = analysis_result if source == "nlp" else analysis_result.get("nlp", {})
        confidence = int(nlp.get("confidence", 0) * 100)
        return templates[risk_level]["fake_news"].format(confidence=confidence)

    # --- Análisis de URL / Levenshtein puro ---
    if source == "levenshtein" or (
        "url_analysis" in analysis_result and "nlp" not in analysis_result
    ):
        url_data = (
            analysis_result if source == "levenshtein"
            else analysis_result.get("url_analysis", {})
        )
        return templates[risk_level]["typosquatting"].format(
            closest_domain=url_data.get("closest_domain", "sitio oficial"),
            extracted_domain=url_data.get("extracted_domain", "dominio desconocido"),
        )

    # --- Análisis de imagen / OCR puro ---
    if source == "image":
        ocr = analysis_result.get("ocr", {})
        extracted_text = ocr.get("extracted_text", "")[:200]  # limitar longitud
        return templates[risk_level]["imagen"].format(
            extracted_text=extracted_text or "texto ilegible"
        )

    # --- Análisis completo (full) ---
    if source in ("full", "image") or len(analysis_result) > 5:
        detalle = _build_detail(analysis_result, channel)
        return templates[risk_level]["combinado"].format(detalle=detalle)

    # Fallback genérico
    return templates[risk_level]["combinado"].format(
        detalle="Se analizó el contenido enviado."
    )


def _build_detail(result: dict, channel: str) -> str:
    """Construye el detalle del mensaje combinado."""
    lines = []

    if "fact_check" in result and result["fact_check"]:
        fc = result["fact_check"]
        veredicto = fc.get("veredicto", "INCIERTO")
        confianza = int(fc.get("confianza", 0) * 100)
        resumen   = (fc.get("resumen") or "")[:180]
        fuente    = fc.get("fuente") or ""

        if veredicto == "FALSO":
            prefix = "• ❌" if channel == "whatsapp" else "•"
            lines.append(f"{prefix} Verificación web: FALSO ({confianza}% confianza)")
            if resumen:
                lines.append(f"  _{resumen}_" if channel == "whatsapp" else f"  {resumen}")
        elif veredicto == "VERDADERO":
            prefix = "• ✅" if channel == "whatsapp" else "•"
            lines.append(f"{prefix} Verificación web: CONFIRMADO ({confianza}%)")
            if resumen:
                lines.append(f"  _{resumen}_" if channel == "whatsapp" else f"  {resumen}")
        else:
            prefix = "• 🔎" if channel == "whatsapp" else "•"
            lines.append(f"{prefix} Verificación web: sin resultados concluyentes")

    if "nlp" in result:
        nlp = result["nlp"]
        label = nlp.get("label", "")
        conf = int(nlp.get("confidence", 0) * 100)
        if label == "FAKE":
            prefix = "• ⚠️" if channel == "whatsapp" else "•"
            lines.append(f"{prefix} Texto sospechoso de ser fake news ({conf}% confianza)")

    if "url_analysis" in result:
        url_data = result["url_analysis"]
        if url_data.get("is_suspicious"):
            closest = url_data.get("closest_domain", "")
            extracted = url_data.get("extracted_domain", "")
            prefix = "• 🔗" if channel == "whatsapp" else "•"
            lines.append(f"{prefix} Enlace imita a '{closest}' → '{extracted}'")

    if "ocr" in result and result["ocr"].get("has_text"):
        prefix = "• 🖼️" if channel == "whatsapp" else "•"
        lines.append(f"{prefix} Se encontró texto en la imagen")

    if "ocr_nlp" in result:
        ocr_nlp = result["ocr_nlp"]
        if ocr_nlp.get("label") == "FAKE":
            conf = int(ocr_nlp.get("confidence", 0) * 100)
            prefix = "• 📸" if channel == "whatsapp" else "•"
            lines.append(f"{prefix} Texto de imagen es sospechoso ({conf}% confianza)")

    return "\n".join(lines) if lines else "Se detectaron señales de alerta."
