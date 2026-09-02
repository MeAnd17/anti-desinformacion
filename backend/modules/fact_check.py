"""
Módulo Fact-Check — Verificación de hechos mediante búsqueda web.

Usa la Google Fact Check Tools API (gratuita) para verificar afirmaciones.
Si no hay API key configurada, usa DuckDuckGo como fallback.

Para activar Google Fact Check:
  1. Obtén una API key en: https://developers.google.com/fact-check/tools/api
  2. Crea el archivo backend/.env con: GOOGLE_FACTCHECK_KEY=tu_api_key
     o exporta la variable: export GOOGLE_FACTCHECK_KEY=tu_api_key
"""

from __future__ import annotations

import os
import re
import json
import urllib.parse
import urllib.request
from typing import Optional

# Cargar variables de entorno desde .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

GOOGLE_API_KEY = os.environ.get("GOOGLE_FACTCHECK_KEY", "")
GOOGLE_FC_URL  = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

# Fuentes confiables para el fallback DuckDuckGo
FUENTES_CONFIABLES_ALTO = [
    "andina.pe", "gob.pe", "minsa.gob.pe", "sunat.gob.pe",
    "bbc.com", "bbc.co.uk", "reuters.com", "apnews.com",
    "elcomercio.pe", "rpp.pe", "larepublica.pe",
    "snopes.com", "factcheck.org", "chequeado.com",
]

KEYWORDS_FALSO = [
    "falso", "fake", "desmentido", "no es cierto", "engaño", "bulo",
    "hoax", "desinformación", "mentira", "rumor", "es falso que",
    "no murió", "sigue vivo", "no ha muerto", "no falleció",
    "false", "misleading", "incorrect",
]

KEYWORDS_VERDADERO = [
    "verdadero", "confirmado", "correcto", "verídico", "true",
    "murió", "falleció", "oficial", "se confirmó", "fallecimiento",
]


# ---------------------------------------------------------------------------
# Google Fact Check Tools API
# ---------------------------------------------------------------------------

def _google_factcheck(query: str) -> Optional[dict]:
    """
    Consulta la Google Fact Check Tools API.
    Busca en español primero, luego en inglés si no hay resultados.
    """
    if not GOOGLE_API_KEY:
        return None

    # Intentar en español y sin filtro de idioma
    for lang in ["es", ""]:
        p = {"query": query[:200], "pageSize": 5, "key": GOOGLE_API_KEY}
        if lang:
            p["languageCode"] = lang
        params = urllib.parse.urlencode(p)

        try:
            req = urllib.request.Request(
                f"{GOOGLE_FC_URL}?{params}",
                headers={"User-Agent": "TucuyBot/1.0"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

        claims = data.get("claims", [])
        if claims:
            break
    else:
        return None  # ningún idioma dio resultados

    # Tomar el primer resultado
    claim  = claims[0]
    review = claim.get("claimReview", [{}])[0]

    rating_text = review.get("textualRating", "").lower()
    publisher   = review.get("publisher", {}).get("name", "")
    url         = review.get("url", "")
    title       = review.get("title", "")

    # Determinar veredicto desde el rating textual
    veredicto  = "INCIERTO"
    confianza  = 0.5

    falso_ratings = ["falso", "false", "incorrect", "misleading", "fake",
                     "engaño", "no", "mentira", "bulo", "mostly false"]
    verdad_ratings = ["verdadero", "true", "correcto", "correct",
                      "mostly true", "accurate", "confirmado"]

    for r in falso_ratings:
        if r in rating_text:
            veredicto = "FALSO"
            confianza = 0.85
            break

    if veredicto == "INCIERTO":
        for r in verdad_ratings:
            if r in rating_text:
                veredicto = "VERDADERO"
                confianza = 0.80
                break

    return {
        "veredicto":   veredicto,
        "confianza":   confianza,
        "fuente":      url,
        "resumen":     f"{title} — Calificación: {review.get('textualRating', 'N/A')} ({publisher})",
        "query_usada": query,
        "source":      "google_factcheck",
    }


# ---------------------------------------------------------------------------
# Fallback: DuckDuckGo
# ---------------------------------------------------------------------------

def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """Búsqueda en DuckDuckGo Instant Answer API (sin key)."""
    encoded = urllib.parse.quote(query)
    url = (
        f"https://api.duckduckgo.com/?q={encoded}"
        f"&format=json&no_redirect=1&no_html=1&skip_disambig=1"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TucuyBot/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    results = []
    if data.get("AbstractText"):
        results.append({
            "title":   data.get("Heading", ""),
            "url":     data.get("AbstractURL", ""),
            "snippet": data.get("AbstractText", ""),
        })
    for r in data.get("RelatedTopics", [])[:max_results]:
        if isinstance(r, dict) and r.get("Text"):
            results.append({
                "title":   r.get("Text", "")[:80],
                "url":     r.get("FirstURL", ""),
                "snippet": r.get("Text", ""),
            })
    return results[:max_results]


def _score_ddg(results: list[dict]) -> dict:
    """Puntúa los resultados de DuckDuckGo para determinar veredicto."""
    if not results:
        return {
            "veredicto": "INCIERTO",
            "confianza": 0.0,
            "fuente":    None,
            "resumen":   "No se encontraron resultados públicos para verificar esta afirmación.",
        }

    score_falso = score_verdadero = 0
    mejor_url = mejor_snippet = ""

    for r in results:
        texto = (r.get("snippet", "") + " " + r.get("title", "")).lower()
        url   = r.get("url", "").lower()

        peso = 2 if any(f in url for f in FUENTES_CONFIABLES_ALTO) else 1
        if not mejor_url and r.get("url"):
            mejor_url     = r["url"]
            mejor_snippet = r.get("snippet", "")[:200]

        if any(k in texto for k in KEYWORDS_FALSO):
            score_falso += peso
        if any(k in texto for k in KEYWORDS_VERDADERO):
            score_verdadero += peso

    total = score_falso + score_verdadero
    if total == 0:
        return {
            "veredicto": "INCIERTO",
            "confianza": 0.3,
            "fuente":    mejor_url or None,
            "resumen":   mejor_snippet or "Información insuficiente para verificar.",
        }

    if score_falso > score_verdadero:
        conf = min(0.90, 0.5 + score_falso / (total * 2))
        return {
            "veredicto": "FALSO",
            "confianza": round(conf, 2),
            "fuente":    mejor_url or None,
            "resumen":   mejor_snippet or "Fuentes encontradas contradicen esta afirmación.",
        }
    else:
        conf = min(0.90, 0.5 + score_verdadero / (total * 2))
        return {
            "veredicto": "VERDADERO",
            "confianza": round(conf, 2),
            "fuente":    mejor_url or None,
            "resumen":   mejor_snippet or "Fuentes encontradas respaldan esta afirmación.",
        }


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def verify_claim(text: str) -> dict:
    """
    Verifica una afirmación usando Google Fact Check API (si hay key)
    o DuckDuckGo como fallback.

    Args:
        text: Texto a verificar.

    Returns:
        dict con veredicto, confianza, fuente, resumen, source.
    """
    if not text or not text.strip():
        return {
            "veredicto": "INCIERTO",
            "confianza": 0.0,
            "fuente":    None,
            "resumen":   "Texto vacío.",
            "query_usada": "",
            "source":    "fact_check",
        }

    # Limpiar y preparar query
    clean = re.sub(r"\s+", " ", text.strip().replace("\n", " "))
    query = clean[:150]

    # Intentar Google Fact Check primero
    google_result = _google_factcheck(query)
    if google_result:
        return google_result

    # Fallback: DuckDuckGo
    results = _ddg_search(query)
    score   = _score_ddg(results)

    return {
        **score,
        "query_usada": query,
        "source":      "fact_check_ddg",
    }
