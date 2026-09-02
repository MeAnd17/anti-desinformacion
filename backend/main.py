"""
Sistema Anti-Desinformación — Backend FastAPI
Detecta fake news, typosquatting en URLs y texto malicioso en imágenes.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
import base64

from modules.nlp import classify_text
from modules.levenshtein import analyze_url
from modules.ocr import extract_text_from_image
from modules.formatter import format_response
from modules.fact_check import verify_claim

# ---------------------------------------------------------------------------
# Inicialización de la app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="API Anti-Desinformación",
    description=(
        "Sistema conversacional para detectar desinformación digital, "
        "enlaces fraudulentos y noticias falsas en Lima Metropolitana."
    ),
    version="1.0.0",
)

# CORS — permite peticiones desde la extensión Chrome y el bot local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------


class TextRequest(BaseModel):
    text: str

    model_config = {"json_schema_extra": {"example": {"text": "El gobierno peruano oculta la cura del COVID-19"}}}


class UrlRequest(BaseModel):
    url: str

    model_config = {"json_schema_extra": {"example": {"url": "https://bcp-descuentos.com/oferta"}}}


class FullRequest(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None
    image_base64: Optional[str] = None  # imagen codificada en base64

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "Haz clic aquí para ganar un premio del BCP",
                "url": "https://bcp-premios.com/ganar",
                "image_base64": None,
            }
        }
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Sistema"])
def health_check():
    """Verifica que el servidor está corriendo correctamente."""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/analyze/text", tags=["Análisis"])
def analyze_text_endpoint(request: TextRequest):
    """
    Analiza un texto y determina si es desinformación o fake news.

    Retorna la etiqueta (FAKE/REAL), nivel de confianza y nivel de riesgo.
    """
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=422, detail="El campo 'text' no puede estar vacío.")

    result = classify_text(request.text)
    result["formatted_message"] = format_response(result, channel="api")
    return result


@app.post("/analyze/url", tags=["Análisis"])
def analyze_url_endpoint(request: UrlRequest):
    """
    Analiza una URL y detecta si es un intento de typosquatting
    contra dominios legítimos peruanos.
    """
    if not request.url or not request.url.strip():
        raise HTTPException(status_code=422, detail="El campo 'url' no puede estar vacío.")

    result = analyze_url(request.url)
    result["formatted_message"] = format_response(result, channel="api")
    return result


@app.post("/analyze/image", tags=["Análisis"])
async def analyze_image_endpoint(file: UploadFile = File(...)):
    """
    Recibe una imagen, extrae el texto con OCR y lo analiza con NLP.
    También detecta URLs en el texto extraído.
    """
    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise HTTPException(
            status_code=422,
            detail="Formato de imagen no soportado. Use JPEG, PNG, WEBP o GIF.",
        )

    image_bytes = await file.read()
    ocr_result = extract_text_from_image(image_bytes)

    nlp_result = None
    url_result = None
    fact_result = None

    if ocr_result["has_text"]:
        nlp_result  = classify_text(ocr_result["extracted_text"])
        fact_result = verify_claim(ocr_result["extracted_text"])

        # Si hay URLs en el texto, analizar la primera
        if ocr_result.get("urls_found"):
            url_result = analyze_url(ocr_result["urls_found"][0])

    # Calcular riesgo general
    risks = []
    if nlp_result:
        risks.append(nlp_result.get("risk_level", "bajo"))
    if url_result:
        risks.append(url_result.get("risk_level", "bajo"))
    # Si el fact-check dice FALSO, escalar el riesgo
    if fact_result and fact_result.get("veredicto") == "FALSO":
        conf = fact_result.get("confianza", 0)
        risks.append("alto" if conf >= 0.7 else "medio")

    # Si el texto extraído es muy corto o el fact-check es INCIERTO
    # y el NLP no detectó nada claro → marcar como INCIERTO
    texto_corto = len((ocr_result.get("extracted_text") or "").strip()) < 25
    fact_incierto = not fact_result or fact_result.get("veredicto") == "INCIERTO"
    nlp_bajo = not nlp_result or nlp_result.get("risk_level") == "bajo"

    if texto_corto and fact_incierto and nlp_bajo:
        overall_risk = "incierto"
    else:
        overall_risk = _max_risk(risks)

    combined = {
        "source": "image",
        "ocr": ocr_result,
        "nlp": nlp_result,
        "url_analysis": url_result,
        "fact_check": fact_result,
        "overall_risk_level": overall_risk,
    }
    combined["formatted_message"] = format_response(combined, channel="api")
    return combined


@app.post("/analyze/full", tags=["Análisis"])
async def analyze_full_endpoint(request: FullRequest):
    """
    Endpoint orquestador: recibe texto, URL e imagen (base64) de forma opcional.
    Ejecuta los módulos disponibles según lo que llegue y retorna un resultado unificado.
    """
    if not any([request.text, request.url, request.image_base64]):
        raise HTTPException(
            status_code=422,
            detail="Debe enviar al menos uno de: 'text', 'url' o 'image_base64'.",
        )

    results: dict = {"source": "full"}
    risks = []

    # Análisis de texto
    if request.text and request.text.strip():
        nlp_result  = classify_text(request.text)
        fact_result = verify_claim(request.text)
        results["nlp"]        = nlp_result
        results["fact_check"] = fact_result
        risks.append(nlp_result.get("risk_level", "bajo"))
        if fact_result.get("veredicto") == "FALSO":
            conf = fact_result.get("confianza", 0)
            risks.append("alto" if conf >= 0.7 else "medio")

    # Análisis de URL
    if request.url and request.url.strip():
        url_result = analyze_url(request.url)
        results["url_analysis"] = url_result
        risks.append(url_result.get("risk_level", "bajo"))

    # Análisis de imagen (base64)
    if request.image_base64:
        try:
            image_bytes = base64.b64decode(request.image_base64)
        except Exception:
            raise HTTPException(status_code=422, detail="La imagen en base64 no es válida.")

        ocr_result = extract_text_from_image(image_bytes)
        results["ocr"] = ocr_result

        if ocr_result["has_text"]:
            img_nlp = classify_text(ocr_result["extracted_text"])
            img_fact = verify_claim(ocr_result["extracted_text"])
            results["ocr_nlp"] = img_nlp
            results["fact_check"] = img_fact
            risks.append(img_nlp.get("risk_level", "bajo"))

            if img_fact.get("veredicto") == "FALSO":
                conf = img_fact.get("confianza", 0)
                risks.append("alto" if conf >= 0.7 else "medio")

            if ocr_result.get("urls_found"):
                img_url = analyze_url(ocr_result["urls_found"][0])
                results["ocr_url_analysis"] = img_url
                risks.append(img_url.get("risk_level", "bajo"))

    # Determinar riesgo general
    # Si el único input fue una imagen con texto corto e incierto → marcar incierto
    solo_imagen = request.image_base64 and not request.text and not request.url
    ocr_data = results.get("ocr", {})
    texto_extraido = (ocr_data.get("extracted_text") or "").strip()
    texto_corto = len(texto_extraido) < 25
    fact_data = results.get("fact_check", {})
    fact_incierto = not fact_data or fact_data.get("veredicto") == "INCIERTO"
    nlp_data = results.get("ocr_nlp", {})
    nlp_bajo = not nlp_data or nlp_data.get("risk_level") == "bajo"

    if solo_imagen and texto_corto and fact_incierto and nlp_bajo:
        results["overall_risk_level"] = "incierto"
    else:
        results["overall_risk_level"] = _max_risk(risks)
    results["formatted_message"] = format_response(results, channel="api")
    return results


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

_RISK_ORDER = {"alto": 3, "medio": 2, "bajo": 1, "incierto": 0}


def _max_risk(risk_list: list) -> str:
    """Devuelve el nivel de riesgo más alto de una lista."""
    if not risk_list:
        return "bajo"
    return max(risk_list, key=lambda r: _RISK_ORDER.get(r, 0))
