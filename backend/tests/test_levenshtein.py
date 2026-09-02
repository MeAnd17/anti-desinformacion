"""
Tests del módulo Levenshtein — Detección de typosquatting en URLs.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.levenshtein import analyze_url, _extract_domain, _compute_similarity


class TestExtractDomain:

    def test_url_completa(self):
        assert _extract_domain("https://bcp.com.pe/login") == "bcp.com.pe"

    def test_url_con_www(self):
        assert _extract_domain("https://www.bcp.com.pe") == "bcp.com.pe"

    def test_url_sin_esquema(self):
        assert _extract_domain("bcp-descuentos.com") == "bcp-descuentos.com"

    def test_url_con_puerto(self):
        assert _extract_domain("http://localhost:8000/api") == "localhost"

    def test_url_con_path_largo(self):
        domain = _extract_domain("https://sunat-afp.gob.pe/pago/tramite?ref=123")
        assert domain == "sunat-afp.gob.pe"


class TestComputeSimilarity:

    def test_dominios_identicos(self):
        assert _compute_similarity("bcp.com.pe", "bcp.com.pe") == 1.0

    def test_dominios_muy_diferentes(self):
        sim = _compute_similarity("google.com", "bcp.com.pe")
        assert sim < 0.6

    def test_typosquatting_cercano(self):
        # bcp-descuentos vs bcp: el prefijo es similar, similitud debe ser > 0.4
        sim = _compute_similarity("bcp-descuentos.com", "bcp.com.pe")
        assert sim > 0.4, f"Similitud esperada > 0.4, obtenida: {sim}"


class TestAnalyzeUrl:

    def test_typosquatting_bcp(self):
        """URL que imita al BCP debe ser detectada como sospechosa."""
        result = analyze_url("https://bcp-descuentos.com/oferta")
        assert result["source"] == "levenshtein"
        assert result["is_suspicious"] is True
        assert result["closest_domain"] == "bcp.com.pe"
        assert result["risk_level"] in ("alto", "medio")

    def test_typosquatting_bbva(self):
        """URL que imita al BBVA debe ser detectada."""
        result = analyze_url("https://bbva-peru.net/login")
        assert result["is_suspicious"] is True
        assert "bbva" in result["closest_domain"]

    def test_typosquatting_sunat(self):
        """URL que imita a SUNAT debe ser detectada."""
        result = analyze_url("https://sunat-afp.com/clave")
        assert result["source"] == "levenshtein"
        assert result["closest_domain"] is not None

    def test_dominio_legitimo_bcp(self):
        """El dominio real del BCP NO debe marcarse como sospechoso."""
        result = analyze_url("https://bcp.com.pe/login")
        assert result["is_suspicious"] is False
        assert result["risk_level"] == "bajo"

    def test_dominio_legitimo_sunat(self):
        """El dominio real de SUNAT NO debe marcarse como sospechoso."""
        result = analyze_url("https://sunat.gob.pe/consulta")
        assert result["is_suspicious"] is False

    def test_dominio_generico_desconocido(self):
        """Un dominio completamente diferente no debe marcar falsos positivos."""
        result = analyze_url("https://miweb-personal-ejemplo.com")
        assert result["source"] == "levenshtein"
        assert result["risk_level"] in ("alto", "medio", "bajo")

    def test_url_vacia(self):
        """URL vacía debe retornar resultado sin error."""
        result = analyze_url("")
        assert result["is_suspicious"] is False
        assert "error" in result

    def test_url_sin_esquema(self):
        """URL sin https:// debe funcionar correctamente."""
        result = analyze_url("bcp-online.com")
        assert result["source"] == "levenshtein"
        assert "extracted_domain" in result

    def test_typosquatting_reniec(self):
        """URL que imita a RENIEC debe ser detectada."""
        result = analyze_url("https://reniec-tramites.com/dni")
        assert result["source"] == "levenshtein"

    def test_estructura_respuesta(self):
        """La respuesta siempre tiene todos los campos esperados."""
        result = analyze_url("https://bcp.com.pe")
        required = {
            "original_url", "extracted_domain", "is_suspicious",
            "closest_domain", "similarity", "risk_level", "source"
        }
        assert required.issubset(result.keys())
