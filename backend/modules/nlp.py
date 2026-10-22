"""
Módulo NLP — Clasificación de fake news con RoBERTa en español.

Usa el modelo pre-entrenado de HuggingFace para clasificar texto en español
como FAKE (desinformación) o REAL (información legítima).

Modelo: Narrativaai/fake-news-detection-spanish

En producción (Render) usa la Hugging Face Inference API para no cargar
el modelo en RAM local. En desarrollo local carga el modelo directamente.

Requiere: HF_TOKEN en .env para usar la Inference API.
"""

from __future__ import annotations

import os
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

HF_TOKEN     = os.getenv("HF_TOKEN", "")
MODEL_NAME   = "analuciahm/tucuy-fake-news-spanish"
HF_API_URL   = f"https://api-inference.huggingface.co/models/{MODEL_NAME}"
TIMEOUT_SECS = 30

# Pipeline local (solo se usa si no hay HF_TOKEN)
_pipeline = None


# ---------------------------------------------------------------------------
# Inferencia vía Hugging Face Inference API
# ---------------------------------------------------------------------------

def _classify_via_api(text: str) -> Optional[dict]:
    """
    Llama a la Hugging Face Inference API.
    No requiere cargar el modelo en RAM local.
    """
    headers = {}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"

    try:
        response = requests.post(
            HF_API_URL,
            headers=headers,
            json={"inputs": text[:2000]},
            timeout=TIMEOUT_SECS,
        )

        if response.status_code == 503:
            # Modelo dormido en HF — puede tardar unos segundos en despertar
            logger.warning("[NLP] Modelo en HF está cargando, reintentando...")
            import time
            time.sleep(10)
            response = requests.post(
                HF_API_URL,
                headers=headers,
                json={"inputs": text[:2000]},
                timeout=TIMEOUT_SECS,
            )

        if response.status_code == 200:
            data = response.json()
            # La API devuelve [[{label, score}, ...]]
            if isinstance(data, list) and len(data) > 0:
                results = data[0] if isinstance(data[0], list) else data
                best = max(results, key=lambda x: x["score"])
                return best
        else:
            logger.warning(f"[NLP] HF API error {response.status_code}: {response.text[:200]}")
            return None

    except Exception as e:
        logger.warning(f"[NLP] Error llamando HF API: {e}")
        return None


# ---------------------------------------------------------------------------
# Pipeline local (fallback si no hay HF_TOKEN)
# ---------------------------------------------------------------------------

def _get_pipeline():
    """Carga el pipeline localmente — solo para desarrollo."""
    global _pipeline
    if _pipeline is None:
        if os.getenv("USE_FALLBACK_NLP", "").lower() == "true":
            return None
        try:
            import transformers
            print("[NLP] Cargando modelo RoBERTa localmente...")
            _pipeline = transformers.pipeline(
                task="text-classification",
                model=MODEL_NAME,
                truncation=True,
                max_length=512,
            )
            print("[NLP] Modelo cargado correctamente.")
        except Exception as e:
            print(f"[NLP] Error al cargar modelo local: {e}")
            _pipeline = None
    return _pipeline


# ---------------------------------------------------------------------------
# Funciones de mapeo
# ---------------------------------------------------------------------------

def _map_risk_level(confidence: float, label: str) -> str:
    if label.upper() in ("FAKE", "LABEL_1", "1"):
        if confidence > 0.85:
            return "alto"
        elif confidence >= 0.60:
            return "medio"
        else:
            return "bajo"
    return "bajo"


def _normalize_label(raw_label: str) -> str:
    label = raw_label.upper()
    if label in ("FAKE", "LABEL_1", "1", "FALSO", "DESINFORMACION"):
        return "FAKE"
    return "REAL"


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def classify_text(text: str) -> dict:
    """
    Clasifica un texto como FAKE o REAL.

    Estrategia:
      1. Si hay HF_TOKEN → usa Hugging Face Inference API (sin cargar modelo local)
      2. Si no hay token  → intenta cargar el modelo localmente
      3. Si falla todo   → fallback heurístico por palabras clave

    Args:
        text: Texto a clasificar.

    Returns:
        dict con label, confidence, risk_level, source, model.
    """
    if not text or not text.strip():
        return {
            "label": "REAL", "confidence": 0.0,
            "risk_level": "bajo", "source": "nlp",
            "model": MODEL_NAME, "error": "Texto vacío",
        }

    # --- Estrategia 1: Hugging Face Inference API ---
    if HF_TOKEN:
        api_result = _classify_via_api(text)
        if api_result:
            label      = _normalize_label(api_result["label"])
            confidence = round(float(api_result["score"]), 4)
            risk_level = _map_risk_level(confidence, label)
            return {
                "label":      label,
                "confidence": confidence,
                "risk_level": risk_level,
                "source":     "nlp",
                "model":      MODEL_NAME,
                "inference":  "huggingface_api",
            }
        logger.warning("[NLP] HF API falló, intentando pipeline local...")

    # --- Estrategia 2: pipeline local ---
    pipe = _get_pipeline()
    if pipe:
        try:
            raw_results = pipe(text[:2000])
            best        = raw_results[0]
            label       = _normalize_label(best["label"])
            confidence  = round(float(best["score"]), 4)
            risk_level  = _map_risk_level(confidence, label)
            return {
                "label":      label,
                "confidence": confidence,
                "risk_level": risk_level,
                "source":     "nlp",
                "model":      MODEL_NAME,
                "inference":  "local",
            }
        except Exception as e:
            logger.warning(f"[NLP] Error en pipeline local: {e}")

    # --- Estrategia 3: fallback heurístico ---
    return _fallback_classify(text)


def _fallback_classify(text: str) -> dict:
    """Clasificador heurístico cuando el modelo no está disponible."""
    KEYWORDS_FAKE = [
        "cura milagrosa", "el gobierno oculta", "lo que no quieren que sepas",
        "medicina prohibida", "comparte antes de que borren",
        "urgente", "no quieren que lo veas", "fake", "mentira",
        "confirmado", "última hora", "exclusivo", "alerta máxima",
        "haz clic aquí", "gana dinero", "premio", "ganaste", "seleccionado",
    ]
    text_lower = text.lower()
    matches = sum(1 for kw in KEYWORDS_FAKE if kw in text_lower)

    if matches >= 3:
        confidence, label, risk = 0.78, "FAKE", "medio"
    elif matches >= 1:
        confidence, label, risk = 0.62, "FAKE", "medio"
    else:
        confidence, label, risk = 0.85, "REAL", "bajo"

    return {
        "label": label, "confidence": confidence,
        "risk_level": risk, "source": "nlp",
        "model": "heuristic-fallback",
        "inference": "fallback",
        "note": "Modelo no disponible, usando heurística de palabras clave",
    }
