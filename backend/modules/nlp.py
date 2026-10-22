"""
Módulo NLP — Clasificación de fake news con RoBERTa en español.

Modelo: analuciahm/tucuy-fake-news-spanish (Narrativaai/fake-news-detection-spanish)

En producción (Render free) usa el clasificador heurístico por limitaciones
de infraestructura. En entorno local con GPU/RAM suficiente carga el modelo completo.

Para activar el modelo completo localmente:
  pip install transformers torch
  # Asegurarse de NO tener USE_FALLBACK_NLP=true en .env
"""

from __future__ import annotations

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_NAME = "analuciahm/tucuy-fake-news-spanish"

# Pipeline local (solo disponible con transformers + torch instalados)
_pipeline = None


def _get_pipeline():
    """Intenta cargar el modelo localmente. Solo funciona con transformers instalado."""
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
            print(f"[NLP] Pipeline local no disponible: {e}")
            _pipeline = None
    return _pipeline


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


def classify_text(text: str) -> dict:
    """
    Clasifica un texto como FAKE o REAL.

    Estrategia:
      1. Pipeline local con modelo RoBERTa (requiere transformers + torch)
      2. Fallback heurístico por palabras clave (producción en Render free)
    """
    if not text or not text.strip():
        return {
            "label": "REAL", "confidence": 0.0,
            "risk_level": "bajo", "source": "nlp",
            "model": MODEL_NAME, "error": "Texto vacío",
        }

    # Estrategia 1: pipeline local
    pipe = _get_pipeline()
    if pipe:
        try:
            raw_results = pipe(text[:2000])
            best       = raw_results[0]
            label      = _normalize_label(best["label"])
            confidence = round(float(best["score"]), 4)
            risk_level = _map_risk_level(confidence, label)
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

    # Estrategia 2: fallback heurístico
    return _fallback_classify(text)


def _fallback_classify(text: str) -> dict:
    """Clasificador heurístico cuando el modelo no está disponible."""
    KEYWORDS_FAKE = [
        "cura milagrosa", "el gobierno oculta", "lo que no quieren que sepas",
        "medicina prohibida", "comparte antes de que borren",
        "urgente", "no quieren que lo veas", "mentira",
        "última hora", "exclusivo", "alerta máxima",
        "haz clic aquí", "gana dinero", "premio", "ganaste", "seleccionado",
        "no lo verás en las noticias", "esto es lo que ocultan",
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
        "label":      label,
        "confidence": confidence,
        "risk_level": risk,
        "source":     "nlp",
        "model":      "heuristic-fallback",
        "inference":  "fallback",
        "note":       "Modelo RoBERTa no disponible en este entorno. Usando heurística de palabras clave.",
    }
