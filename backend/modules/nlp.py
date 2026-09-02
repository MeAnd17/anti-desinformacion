"""
Módulo NLP — Clasificación de fake news con RoBERTa en español.

Usa el modelo pre-entrenado de HuggingFace para clasificar texto en español
como FAKE (desinformación) o REAL (información legítima).

Modelo: Narrativaai/fake-news-detection-spanish
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

# transformers se importa dentro de la función para controlar el tiempo de arranque
_pipeline = None


def _get_pipeline():
    """Carga el pipeline de clasificación de texto de forma perezosa (lazy loading)."""
    global _pipeline
    if _pipeline is None:
        try:
            import transformers
            hf_pipeline = transformers.pipeline

            print("[NLP] Cargando modelo fake-news-detection-spanish (RoBERTa)...")
            _pipeline = hf_pipeline(
                task="text-classification",
                model="Narrativaai/fake-news-detection-spanish",
                truncation=True,
                max_length=512,
            )
            print("[NLP] Modelo cargado correctamente.")
        except Exception as e:
            print(f"[NLP] Error al cargar el modelo: {e}")
            _pipeline = None
    return _pipeline


def _map_risk_level(confidence: float, label: str) -> str:
    """
    Mapea la confianza del modelo a un nivel de riesgo comprensible.

    Para etiquetas FAKE:
      - confianza > 0.85 → alto
      - confianza 0.60–0.85 → medio
      - confianza < 0.60 → bajo

    Para etiquetas REAL, el riesgo es siempre bajo.
    """
    if label.upper() in ("FAKE", "LABEL_1", "1"):
        if confidence > 0.85:
            return "alto"
        elif confidence >= 0.60:
            return "medio"
        else:
            return "bajo"
    return "bajo"


def _normalize_label(raw_label: str) -> str:
    """Normaliza etiquetas del modelo a FAKE/REAL."""
    label = raw_label.upper()
    if label in ("FAKE", "LABEL_1", "1", "FALSO", "DESINFORMACION"):
        return "FAKE"
    return "REAL"


def classify_text(text: str) -> dict:
    """
    Clasifica un texto como FAKE o REAL usando BETO fine-tuned.

    Args:
        text: Texto a clasificar (máximo 512 tokens internamente).

    Returns:
        dict con claves:
            - label: "FAKE" o "REAL"
            - confidence: float entre 0 y 1
            - risk_level: "alto", "medio" o "bajo"
            - source: "nlp"
            - model: nombre del modelo usado
    """
    if not text or not text.strip():
        return {
            "label": "REAL",
            "confidence": 0.0,
            "risk_level": "bajo",
            "source": "nlp",
            "model": "beto-fake-news",
            "error": "Texto vacío",
        }

    pipe = _get_pipeline()

    # Si el modelo no está disponible, usar heurística básica como fallback
    if pipe is None:
        return _fallback_classify(text)

    try:
        # El pipeline trunca automáticamente a 512 tokens
        raw_results = pipe(text[:2000])  # limitamos chars para no sobrecargar
        best = raw_results[0]

        label = _normalize_label(best["label"])
        confidence = round(float(best["score"]), 4)
        risk_level = _map_risk_level(confidence, label)

        return {
            "label": label,
            "confidence": confidence,
            "risk_level": risk_level,
            "source": "nlp",
            "model": "Narrativaai/fake-news-detection-spanish",
        }

    except Exception as e:
        print(f"[NLP] Error durante clasificación: {e}")
        return _fallback_classify(text)


def _fallback_classify(text: str) -> dict:
    """
    Clasificador heurístico de emergencia cuando el modelo no está disponible.
    Busca palabras clave de alerta frecuentes en desinformación en español.
    """
    KEYWORDS_FAKE = [
        "cura milagrosa", "el gobierno oculta", "lo que no quieren que sepas",
        "medicina prohibida", "esto es lo que pasa realmente", "comparte antes de que borren",
        "urgente", "no quieren que lo veas", "the truth about", "fake", "mentira",
        "confirmado", "última hora", "exclusivo", "alerta máxima", "esto es verdad",
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
        "label": label,
        "confidence": confidence,
        "risk_level": risk,
        "source": "nlp",
        "model": "heuristic-fallback",
        "note": "Modelo no disponible, usando heurística de palabras clave",
    }
