"""
Módulo NLP — Clasificación de fake news con RoBERTa ONNX cuantizado.

Usa el modelo analuciahm/tucuy-fake-news-spanish-onnx (119MB, int8)
cargado con onnxruntime — sin torch, sin transformers completo.
Cabe en los 512MB de RAM de Render free.

Modelo base: PlanTL-GOB-ES/roberta-large-bne
Fine-tuned con: FakeDeS corpus (IberLEF 2021)
"""

from __future__ import annotations

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ONNX_MODEL_ID = "analuciahm/tucuy-fake-news-spanish-onnx"
MODEL_NAME     = "analuciahm/tucuy-fake-news-spanish"

# Pipeline ONNX — cargado en lazy loading
_onnx_pipeline = None


def _get_onnx_pipeline():
    """Carga el modelo ONNX cuantizado (119MB) en lazy loading."""
    global _onnx_pipeline
    if _onnx_pipeline is None:
        try:
            from optimum.onnxruntime import ORTModelForSequenceClassification
            from transformers import AutoTokenizer, pipeline

            print(f"[NLP] Cargando modelo ONNX desde {ONNX_MODEL_ID}...")
            tokenizer = AutoTokenizer.from_pretrained(ONNX_MODEL_ID)
            model     = ORTModelForSequenceClassification.from_pretrained(ONNX_MODEL_ID)

            _onnx_pipeline = pipeline(
                "text-classification",
                model=model,
                tokenizer=tokenizer,
                truncation=True,
                max_length=512,
            )
            print("[NLP] Modelo ONNX cargado correctamente.")
        except Exception as e:
            print(f"[NLP] No se pudo cargar modelo ONNX: {e}")
            _onnx_pipeline = None
    return _onnx_pipeline


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
      1. Modelo ONNX cuantizado (119MB, cabe en Render free)
      2. Fallback heurístico si ONNX no está disponible
    """
    if not text or not text.strip():
        return {
            "label": "REAL", "confidence": 0.0,
            "risk_level": "bajo", "source": "nlp",
            "model": MODEL_NAME, "error": "Texto vacío",
        }

    # Estrategia 1: modelo ONNX
    pipe = _get_onnx_pipeline()
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
                "inference":  "onnx",
            }
        except Exception as e:
            logger.warning(f"[NLP] Error en pipeline ONNX: {e}")

    # Estrategia 2: fallback heurístico
    return _fallback_classify(text)


def _fallback_classify(text: str) -> dict:
    """Clasificador heurístico cuando el modelo ONNX no está disponible."""
    KEYWORDS_FAKE = [
        "cura milagrosa", "el gobierno oculta", "lo que no quieren que sepas",
        "medicina prohibida", "comparte antes de que borren",
        "urgente", "no quieren que lo veas", "mentira",
        "última hora", "exclusivo", "alerta máxima",
        "haz clic aquí", "gana dinero", "premio", "ganaste", "seleccionado",
        "no lo verás en las noticias", "esto es lo que ocultan",
        "murió", "murio", "falleció", "fallecio", "está muerto",
        "vacuna mata", "chip en la vacuna", "5g causa", "no te vacunes",
        "ivermectina cura", "dióxido de cloro",
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
        "note":       "Modelo ONNX no disponible. Usando heurística de palabras clave.",
    }
