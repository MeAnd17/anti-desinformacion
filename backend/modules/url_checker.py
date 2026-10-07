"""
Módulo URL Checker — Verificación global de URLs maliciosas.

Orquesta múltiples fuentes externas para detectar phishing y malware:
  1. Google Safe Browsing API v4  — cobertura global masiva
  2. URLhaus (abuse.ch)           — malware activo en tiempo real
  3. OpenPhish                    — feed de phishing activo (caché local)
  4. PhishTank                    — base de datos comunitaria de phishing

El módulo opera con degradación elegante: si una fuente no está disponible
o no tiene API key configurada, se omite sin interrumpir el análisis.
"""

from __future__ import annotations

import os
import time
import hashlib
import logging
import asyncio
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración desde variables de entorno
# ---------------------------------------------------------------------------

GOOGLE_SAFE_BROWSING_KEY = os.getenv("GOOGLE_SAFE_BROWSING_KEY", "")
URLHAUS_AUTH_KEY         = os.getenv("URLHAUS_AUTH_KEY", "")
# PhishTank y OpenPhish no requieren key

TIMEOUT_SECONDS = 8  # timeout por llamada externa

# ---------------------------------------------------------------------------
# Caché local de OpenPhish
# ---------------------------------------------------------------------------

_openphish_cache: set[str] = set()
_openphish_last_update: float = 0.0
_OPENPHISH_TTL = 3600  # actualizar cada 1 hora
_OPENPHISH_FEED_URL = "https://openphish.com/feed.txt"


def _refresh_openphish_cache() -> None:
    """Descarga el feed de OpenPhish y actualiza el caché local."""
    global _openphish_cache, _openphish_last_update

    now = time.time()
    if now - _openphish_last_update < _OPENPHISH_TTL and _openphish_cache:
        return  # caché vigente

    try:
        response = requests.get(
            _OPENPHISH_FEED_URL,
            timeout=TIMEOUT_SECONDS,
            headers={"User-Agent": "Tucuy-AntiPhishing/1.0"},
        )
        if response.status_code == 200:
            urls = set(line.strip() for line in response.text.splitlines() if line.strip())
            # Extraer solo los dominios para búsqueda más rápida
            domains = set()
            for url in urls:
                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc.lower().lstrip("www.")
                    if domain:
                        domains.add(domain)
                except Exception:
                    pass
            _openphish_cache = domains
            _openphish_last_update = now
            logger.info(f"[OpenPhish] Caché actualizado: {len(domains)} dominios")
    except Exception as e:
        logger.warning(f"[OpenPhish] No se pudo actualizar el caché: {e}")


# ---------------------------------------------------------------------------
# 1. Google Safe Browsing API v4
# ---------------------------------------------------------------------------

def check_google_safe_browsing(url: str) -> dict:
    """
    Consulta Google Safe Browsing API v4.
    Detecta: phishing, malware, unwanted software, social engineering.

    Requiere: GOOGLE_SAFE_BROWSING_KEY en .env
    Documentación: https://developers.google.com/safe-browsing/v4/lookup-api
    """
    if not GOOGLE_SAFE_BROWSING_KEY:
        return {"source": "google_safe_browsing", "available": False, "reason": "API key no configurada"}

    endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={GOOGLE_SAFE_BROWSING_KEY}"

    payload = {
        "client": {
            "clientId": "tucuy-antidesinformacion",
            "clientVersion": "1.0.0",
        },
        "threatInfo": {
            "threatTypes": [
                "MALWARE",
                "SOCIAL_ENGINEERING",       # phishing
                "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION",
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    try:
        response = requests.post(endpoint, json=payload, timeout=TIMEOUT_SECONDS)
        if response.status_code == 200:
            data = response.json()
            matches = data.get("matches", [])
            if matches:
                threat_type = matches[0].get("threatType", "UNKNOWN")
                return {
                    "source": "google_safe_browsing",
                    "available": True,
                    "is_malicious": True,
                    "threat_type": threat_type,
                    "risk_level": "alto",
                    "reason": f"Google Safe Browsing: {_translate_threat(threat_type)}",
                }
            return {
                "source": "google_safe_browsing",
                "available": True,
                "is_malicious": False,
                "risk_level": "bajo",
                "reason": "No encontrado en Google Safe Browsing",
            }
        else:
            logger.warning(f"[GSB] Error {response.status_code}: {response.text[:200]}")
            return {"source": "google_safe_browsing", "available": False, "reason": f"Error HTTP {response.status_code}"}
    except Exception as e:
        logger.warning(f"[GSB] Excepción: {e}")
        return {"source": "google_safe_browsing", "available": False, "reason": str(e)}


def _translate_threat(threat_type: str) -> str:
    translations = {
        "MALWARE": "Distribuye malware",
        "SOCIAL_ENGINEERING": "Phishing o ingeniería social",
        "UNWANTED_SOFTWARE": "Software no deseado",
        "POTENTIALLY_HARMFUL_APPLICATION": "Aplicación potencialmente dañina",
    }
    return translations.get(threat_type, threat_type)


# ---------------------------------------------------------------------------
# 2. URLhaus (abuse.ch)
# ---------------------------------------------------------------------------

def check_urlhaus(url: str) -> dict:
    """
    Consulta URLhaus de abuse.ch para detectar URLs que distribuyen malware.

    Requiere: URLHAUS_AUTH_KEY en .env (registro gratuito en abuse.ch)
    Documentación: https://urlhaus-api.abuse.ch/
    """
    if not URLHAUS_AUTH_KEY:
        return {"source": "urlhaus", "available": False, "reason": "Auth-Key no configurada"}

    endpoint = "https://urlhaus-api.abuse.ch/v1/url/"

    try:
        response = requests.post(
            endpoint,
            data={"url": url},
            headers={"Auth-Key": URLHAUS_AUTH_KEY},
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code == 200:
            data = response.json()
            query_status = data.get("query_status", "")

            if query_status == "is_host":
                url_status = data.get("url_status", "unknown")
                tags = data.get("tags") or []
                threat = data.get("threat", "malware_download")

                return {
                    "source": "urlhaus",
                    "available": True,
                    "is_malicious": True,
                    "url_status": url_status,
                    "threat": threat,
                    "tags": tags,
                    "risk_level": "alto" if url_status == "online" else "medio",
                    "reason": f"URLhaus: URL registrada como {threat}. Estado: {url_status}",
                }
            elif query_status == "no_results":
                return {
                    "source": "urlhaus",
                    "available": True,
                    "is_malicious": False,
                    "risk_level": "bajo",
                    "reason": "No encontrado en URLhaus",
                }
            else:
                return {"source": "urlhaus", "available": False, "reason": f"Query status inesperado: {query_status}"}
        else:
            return {"source": "urlhaus", "available": False, "reason": f"Error HTTP {response.status_code}"}
    except Exception as e:
        logger.warning(f"[URLhaus] Excepción: {e}")
        return {"source": "urlhaus", "available": False, "reason": str(e)}


# ---------------------------------------------------------------------------
# 3. OpenPhish (feed público, caché local)
# ---------------------------------------------------------------------------

def check_openphish(url: str) -> dict:
    """
    Verifica si la URL o su dominio están en el feed activo de OpenPhish.
    El feed se descarga y cachea localmente — no requiere API key.

    Feed: https://openphish.com/feed.txt (actualizado cada 12h por OpenPhish)
    """
    _refresh_openphish_cache()

    if not _openphish_cache:
        return {"source": "openphish", "available": False, "reason": "Feed no disponible temporalmente"}

    try:
        parsed = urlparse(url if url.startswith("http") else "https://" + url)
        domain = parsed.netloc.lower().lstrip("www.")

        if domain in _openphish_cache:
            return {
                "source": "openphish",
                "available": True,
                "is_malicious": True,
                "risk_level": "alto",
                "reason": f"OpenPhish: dominio '{domain}' detectado en feed de phishing activo",
            }
        return {
            "source": "openphish",
            "available": True,
            "is_malicious": False,
            "risk_level": "bajo",
            "reason": "No encontrado en OpenPhish",
        }
    except Exception as e:
        logger.warning(f"[OpenPhish] Excepción: {e}")
        return {"source": "openphish", "available": False, "reason": str(e)}


# ---------------------------------------------------------------------------
# 4. PhishTank
# ---------------------------------------------------------------------------

def check_phishtank(url: str) -> dict:
    """
    Consulta PhishTank para verificar si una URL es phishing conocido.
    No requiere API key para consultas básicas.

    Documentación: https://www.phishtank.com/api_info.php
    """
    PHISHTANK_APP_KEY = os.getenv("PHISHTANK_APP_KEY", "")

    endpoint = "https://checkurl.phishtank.com/checkurl/"

    # PhishTank requiere el URL en formato url-encoded
    import urllib.parse
    encoded_url = urllib.parse.quote(url, safe="")

    payload = {
        "url": encoded_url,
        "format": "json",
    }
    if PHISHTANK_APP_KEY:
        payload["app_key"] = PHISHTANK_APP_KEY

    try:
        response = requests.post(
            endpoint,
            data=payload,
            headers={
                "User-Agent": "phishtank/Tucuy-AntiDesinformacion",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", {})
            in_database = results.get("in_database", False)
            valid = results.get("valid", False)

            if in_database and valid:
                phish_detail = results.get("phish_detail_url", "")
                return {
                    "source": "phishtank",
                    "available": True,
                    "is_malicious": True,
                    "risk_level": "alto",
                    "reason": f"PhishTank: URL verificada como phishing activo",
                    "detail_url": phish_detail,
                }
            elif in_database and not valid:
                return {
                    "source": "phishtank",
                    "available": True,
                    "is_malicious": False,
                    "risk_level": "bajo",
                    "reason": "PhishTank: URL en base de datos pero marcada como inválida/expirada",
                }
            return {
                "source": "phishtank",
                "available": True,
                "is_malicious": False,
                "risk_level": "bajo",
                "reason": "No encontrado en PhishTank",
            }
        elif response.status_code == 509:
            return {"source": "phishtank", "available": False, "reason": "Límite de solicitudes alcanzado (PhishTank)"}
        else:
            return {"source": "phishtank", "available": False, "reason": f"Error HTTP {response.status_code}"}
    except Exception as e:
        logger.warning(f"[PhishTank] Excepción: {e}")
        return {"source": "phishtank", "available": False, "reason": str(e)}


# ---------------------------------------------------------------------------
# Orquestador principal
# ---------------------------------------------------------------------------

def check_url_external(url: str) -> dict:
    """
    Ejecuta todas las verificaciones externas disponibles para una URL.
    Opera con degradación elegante: omite fuentes no disponibles.

    Retorna:
        dict con:
          - is_malicious: bool
          - risk_level: "alto" | "medio" | "bajo"
          - sources_checked: list de fuentes consultadas
          - detections: list de detecciones positivas
          - all_results: dict completo por fuente
    """
    results = {}

    # Ejecutar todas las fuentes
    results["google_safe_browsing"] = check_google_safe_browsing(url)
    results["urlhaus"]              = check_urlhaus(url)
    results["openphish"]            = check_openphish(url)
    results["phishtank"]            = check_phishtank(url)

    # Consolidar resultados
    sources_checked = [s for s, r in results.items() if r.get("available", False)]
    detections      = [r for r in results.values() if r.get("is_malicious", False)]

    # Nivel de riesgo más alto encontrado
    risk_levels = [d.get("risk_level", "bajo") for d in detections]
    _RISK_ORDER = {"alto": 3, "medio": 2, "bajo": 1}
    overall_risk = max(risk_levels, key=lambda r: _RISK_ORDER.get(r, 0)) if risk_levels else "bajo"

    # Construir razón consolidada
    reasons = [d["reason"] for d in detections if d.get("reason")]

    return {
        "is_malicious":    len(detections) > 0,
        "risk_level":      overall_risk,
        "sources_checked": sources_checked,
        "detections":      detections,
        "reasons":         reasons,
        "all_results":     results,
    }
