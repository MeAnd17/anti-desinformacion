"""
Módulo OCR — Extracción de texto desde imágenes.

Usa OCR.space API (https://ocr.space) para extraer texto en español.
No requiere instalación de Tesseract — funciona como servicio externo.

Requiere: OCR_SPACE_KEY en .env
Obtener key gratuita en: https://ocr.space/ocrapi
"""

from __future__ import annotations

import io
import os
import re
import base64
import logging
from typing import List

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

OCR_SPACE_KEY     = os.getenv("OCR_SPACE_KEY", "")
OCR_SPACE_URL     = "https://api.ocr.space/parse/image"
TIMEOUT_SECONDS   = 30

# Regex para detectar URLs dentro del texto extraído
_URL_PATTERN = re.compile(
    r"(?:https?://|www\.)"
    r"[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+"
    r"(?<![.,;:!?'\"])",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def extract_text_from_image(image_bytes: bytes) -> dict:
    """
    Extrae texto de una imagen usando OCR.space API.

    Args:
        image_bytes: Bytes de la imagen (JPEG, PNG, WebP, GIF).

    Returns:
        dict con claves:
            - extracted_text: texto extraído (str)
            - has_text: bool — si se encontró texto significativo
            - confidence: float estimado de calidad de extracción
            - urls_found: lista de URLs detectadas en el texto
            - source: "ocr"
    """
    if not image_bytes:
        return _error_result("No se recibieron bytes de imagen.")

    if not OCR_SPACE_KEY:
        return _error_result("OCR_SPACE_KEY no configurada en variables de entorno.")

    try:
        # Codificar imagen en base64 para enviar a la API
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Detectar tipo de imagen por magic bytes
        mime_type = _detect_mime(image_bytes)
        image_data = f"data:{mime_type};base64,{image_b64}"

        payload = {
            "base64image":        image_data,
            "language":           "spa",        # español
            "isOverlayRequired":  False,
            "detectOrientation":  True,
            "scale":              True,          # mejora imágenes pequeñas
            "OCREngine":          2,             # motor más preciso
            "isTable":            False,
        }

        response = requests.post(
            OCR_SPACE_URL,
            data=payload,
            headers={"apikey": OCR_SPACE_KEY},
            timeout=TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            return _error_result(f"OCR.space respondió con HTTP {response.status_code}")

        data = response.json()

        # Verificar errores de la API
        if data.get("IsErroredOnProcessing"):
            error_msg = data.get("ErrorMessage", ["Error desconocido"])
            if isinstance(error_msg, list):
                error_msg = error_msg[0]
            return _error_result(f"OCR.space error: {error_msg}")

        # Extraer texto de todos los resultados
        parsed_results = data.get("ParsedResults", [])
        if not parsed_results:
            return _empty_result()

        text_parts = []
        confidences = []

        for result in parsed_results:
            parsed_text = result.get("ParsedText", "").strip()
            if parsed_text:
                text_parts.append(parsed_text)
            # OCR.space no siempre devuelve confianza, usar MeanConfidence si existe
            conf = result.get("TextOverlay", {})

        text = "\n".join(text_parts).strip()
        # Limpiar múltiples saltos de línea
        text = re.sub(r"\n{3,}", "\n\n", text)

        has_text     = len(text.replace(" ", "").replace("\n", "")) >= 10
        urls_found   = _detect_urls(text) if has_text else []
        confidence   = min(1.0, len(text) / 200) if has_text else 0.0

        logger.info(f"[OCR] Texto extraído: {len(text)} caracteres, has_text={has_text}")

        return {
            "extracted_text": text,
            "has_text":       has_text,
            "confidence":     round(confidence, 2),
            "urls_found":     urls_found,
            "source":         "ocr",
        }

    except requests.exceptions.Timeout:
        return _error_result("OCR.space tardó demasiado en responder.")
    except Exception as e:
        logger.error(f"[OCR] Error inesperado: {e}")
        return _error_result(f"Error durante OCR: {e}")


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def _detect_mime(image_bytes: bytes) -> str:
    """Detecta el MIME type por magic bytes."""
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"  # fallback


def _detect_urls(text: str) -> List[str]:
    """Detecta y retorna todas las URLs encontradas en el texto."""
    return _URL_PATTERN.findall(text)


def _error_result(error_msg: str) -> dict:
    """Retorna un resultado de error estandarizado."""
    logger.warning(f"[OCR] {error_msg}")
    return {
        "extracted_text": "",
        "has_text":       False,
        "confidence":     0.0,
        "urls_found":     [],
        "source":         "ocr",
        "error":          error_msg,
    }


def _empty_result() -> dict:
    """Retorna resultado vacío cuando no se encontró texto."""
    return {
        "extracted_text": "",
        "has_text":       False,
        "confidence":     0.0,
        "urls_found":     [],
        "source":         "ocr",
    }
