"""
Módulo OCR — Extracción de texto desde imágenes.

Usa pytesseract + Pillow para preprocesar la imagen y extraer texto en español.
También detecta URLs dentro del texto extraído usando expresiones regulares.
"""

from __future__ import annotations

import io
import re
from typing import List

try:
    from PIL import Image, ImageEnhance, ImageFilter
    import pytesseract
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False
    print("[OCR] AVISO: pytesseract o Pillow no están instalados.")


# Regex para detectar URLs dentro del texto extraído
_URL_PATTERN = re.compile(
    r"(?:https?://|www\.)"          # esquema o www
    r"[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+"
    r"(?<![.,;:!?'\"])",            # no terminar con puntuación
    re.IGNORECASE,
)


def _preprocess_image(image: "Image.Image") -> "Image.Image":
    """
    Aplica preprocesamiento para mejorar la calidad del OCR:
    1. Convierte a escala de grises
    2. Aumenta el contraste
    3. Aplica nitidez
    4. Escala la imagen si es muy pequeña
    """
    # Convertir a escala de grises
    gray = image.convert("L")

    # Aumentar contraste
    enhancer = ImageEnhance.Contrast(gray)
    contrasted = enhancer.enhance(2.0)

    # Aumentar nitidez
    sharpener = ImageEnhance.Sharpness(contrasted)
    sharpened = sharpener.enhance(2.0)

    # Escalar si la imagen es pequeña (mejora OCR en imágenes de baja resolución)
    width, height = sharpened.size
    if width < 800:
        scale = 800 / width
        new_size = (int(width * scale), int(height * scale))
        sharpened = sharpened.resize(new_size, Image.LANCZOS)

    return sharpened


def _detect_urls(text: str) -> List[str]:
    """Detecta y retorna todas las URLs encontradas en el texto."""
    return _URL_PATTERN.findall(text)


def extract_text_from_image(image_bytes: bytes) -> dict:
    """
    Extrae texto de una imagen usando OCR.

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
    if not _OCR_AVAILABLE:
        return {
            "extracted_text": "",
            "has_text": False,
            "confidence": 0.0,
            "urls_found": [],
            "source": "ocr",
            "error": "pytesseract no está instalado en el sistema.",
        }

    if not image_bytes:
        return {
            "extracted_text": "",
            "has_text": False,
            "confidence": 0.0,
            "urls_found": [],
            "source": "ocr",
            "error": "No se recibieron bytes de imagen.",
        }

    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        return {
            "extracted_text": "",
            "has_text": False,
            "confidence": 0.0,
            "urls_found": [],
            "source": "ocr",
            "error": f"No se pudo abrir la imagen: {e}",
        }

    try:
        processed = _preprocess_image(image)

        # Configuración de tesseract: idioma español + modo de página automático
        custom_config = r"--oem 3 --psm 3 -l spa"
        text = pytesseract.image_to_string(processed, config=custom_config)

        # Limpiar el texto extraído
        text = text.strip()
        # Eliminar líneas completamente vacías múltiples
        text = re.sub(r"\n{3,}", "\n\n", text)

        has_text = len(text.replace(" ", "").replace("\n", "")) >= 10
        urls_found = _detect_urls(text)

        # Estimación de confianza basada en la cantidad de texto legible
        confidence = min(1.0, len(text) / 200) if has_text else 0.0

        return {
            "extracted_text": text,
            "has_text": has_text,
            "confidence": round(confidence, 2),
            "urls_found": urls_found,
            "source": "ocr",
        }

    except Exception as e:
        return {
            "extracted_text": "",
            "has_text": False,
            "confidence": 0.0,
            "urls_found": [],
            "source": "ocr",
            "error": f"Error durante OCR: {e}",
        }
