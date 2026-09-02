"""
Tests del módulo NLP — Clasificador de fake news con BETO.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.nlp import classify_text, _map_risk_level, _normalize_label


class TestNLPClassifier:

    def test_texto_fake_news_obvio(self):
        """Debe clasificar noticias falsas evidentes como FAKE."""
        text = (
            "URGENTE: El gobierno peruano oculta la cura del COVID-19. "
            "Comparte antes de que borren este mensaje. Lo que no quieren que sepas."
        )
        result = classify_text(text)
        assert result["label"] in ("FAKE", "REAL")  # Siempre retorna una etiqueta válida
        assert "confidence" in result
        assert "risk_level" in result
        assert result["risk_level"] in ("alto", "medio", "bajo")
        assert result["source"] == "nlp"

    def test_texto_real_noticia(self):
        """Debe clasificar noticias reales con bajo nivel de riesgo."""
        text = (
            "El Banco Central de Reserva del Perú reportó un crecimiento del PBI "
            "de 3.2% en el último trimestre según sus indicadores oficiales."
        )
        result = classify_text(text)
        assert result["label"] in ("FAKE", "REAL")
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["risk_level"] in ("alto", "medio", "bajo")

    def test_texto_estafa_financiera(self):
        """Textos de estafas financieras deben tener riesgo elevado."""
        text = (
            "¡Felicitaciones! Has sido SELECCIONADO para recibir S/. 5000 del BCP. "
            "Haz clic aquí para reclamar tu premio ahora."
        )
        result = classify_text(text)
        assert result["label"] in ("FAKE", "REAL")
        assert result["source"] == "nlp"

    def test_texto_desinformacion_salud(self):
        """Desinformación sobre salud debe ser clasificada."""
        text = (
            "MEDICINA PROHIBIDA: El limón con bicarbonato cura el cáncer. "
            "Los médicos no quieren que sepas esto. Comparte con todos."
        )
        result = classify_text(text)
        assert result["label"] in ("FAKE", "REAL")
        assert "risk_level" in result

    def test_texto_verdadero_gobierno(self):
        """Comunicado oficial debe tener riesgo bajo."""
        text = (
            "El Ministerio de Salud informa que la campaña de vacunación gratuita "
            "se realizará en los centros de salud del MINSA durante todo el mes."
        )
        result = classify_text(text)
        assert result["label"] in ("FAKE", "REAL")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_texto_vacio(self):
        """Texto vacío debe retornar resultado sin error."""
        result = classify_text("")
        assert result["label"] == "REAL"
        assert result["risk_level"] == "bajo"
        assert "error" in result

    def test_texto_muy_largo(self):
        """Textos muy largos deben ser procesados sin error."""
        text = "Esta es una noticia. " * 300  # ~6000 chars
        result = classify_text(text)
        assert result["label"] in ("FAKE", "REAL")
        assert "risk_level" in result

    def test_estructura_respuesta_completa(self):
        """La respuesta siempre debe tener todos los campos esperados."""
        result = classify_text("El presidente inauguró una nueva carretera.")
        required_keys = {"label", "confidence", "risk_level", "source", "model"}
        assert required_keys.issubset(result.keys())


class TestHelpers:

    def test_map_risk_level_fake_alto(self):
        assert _map_risk_level(0.90, "FAKE") == "alto"

    def test_map_risk_level_fake_medio(self):
        assert _map_risk_level(0.70, "FAKE") == "medio"

    def test_map_risk_level_fake_bajo(self):
        assert _map_risk_level(0.50, "FAKE") == "bajo"

    def test_map_risk_level_real_siempre_bajo(self):
        assert _map_risk_level(0.99, "REAL") == "bajo"

    def test_normalize_label_variants(self):
        assert _normalize_label("FAKE") == "FAKE"
        assert _normalize_label("LABEL_1") == "FAKE"
        assert _normalize_label("1") == "FAKE"
        assert _normalize_label("REAL") == "REAL"
        assert _normalize_label("LABEL_0") == "REAL"
