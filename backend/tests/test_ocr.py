"""
Tests del módulo OCR — Extracción de texto desde imágenes.
"""

import pytest
import sys
import os
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.ocr import extract_text_from_image, _detect_urls


class TestDetectUrls:

    def test_detecta_url_http(self):
        urls = _detect_urls("Visita http://bcp-descuentos.com para más info")
        assert len(urls) >= 1
        assert any("bcp-descuentos.com" in u for u in urls)

    def test_detecta_url_https(self):
        urls = _detect_urls("Haz clic en https://sunat.gob.pe/tramite")
        assert len(urls) >= 1

    def test_detecta_url_www(self):
        urls = _detect_urls("Ve a www.bbva.pe para ingresar")
        assert len(urls) >= 1

    def test_no_detecta_sin_url(self):
        urls = _detect_urls("Este texto no tiene ningún enlace web")
        assert len(urls) == 0

    def test_detecta_multiples_urls(self):
        text = "Ve a http://sitio1.com y también a https://sitio2.pe"
        urls = _detect_urls(text)
        assert len(urls) >= 2


class TestExtractTextFromImage:

    def test_imagen_bytes_vacios(self):
        """Bytes vacíos deben retornar resultado sin error."""
        result = extract_text_from_image(b"")
        assert result["has_text"] is False
        assert "error" in result

    def test_imagen_invalida(self):
        """Datos no válidos como imagen deben retornar error manejado."""
        result = extract_text_from_image(b"esto no es una imagen valida 12345")
        assert result["has_text"] is False
        assert "error" in result

    def test_estructura_respuesta(self):
        """La respuesta siempre tiene todos los campos esperados."""
        result = extract_text_from_image(b"")
        required = {"extracted_text", "has_text", "confidence", "urls_found", "source"}
        assert required.issubset(result.keys())

    def test_imagen_png_simple(self):
        """Prueba con una imagen PNG mínima válida (1x1 pixel blanco)."""
        try:
            from PIL import Image
            import io as _io

            img = Image.new("RGB", (200, 50), color=(255, 255, 255))
            buf = _io.BytesIO()
            img.save(buf, format="PNG")
            image_bytes = buf.getvalue()

            result = extract_text_from_image(image_bytes)
            # Una imagen en blanco no debería tener texto significativo
            assert result["source"] == "ocr"
            assert "extracted_text" in result
            assert "urls_found" in result
        except ImportError:
            pytest.skip("Pillow no está instalado")

    def test_source_siempre_ocr(self):
        """El campo source siempre debe ser 'ocr'."""
        result = extract_text_from_image(b"")
        assert result["source"] == "ocr"
