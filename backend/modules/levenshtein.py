"""
Módulo Levenshtein — Detección de typosquatting en URLs.

Calcula la distancia de Levenshtein entre el dominio de una URL y cada
dominio legítimo peruano conocido. Si la similitud es alta pero el dominio
no es exactamente igual, se marca como sospechoso.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

try:
    from Levenshtein import distance as levenshtein_distance
except ImportError:
    # Fallback manual si la librería no está instalada
    def levenshtein_distance(s1: str, s2: str) -> int:  # type: ignore[misc]
        if len(s1) < len(s2):
            return levenshtein_distance(s2, s1)
        if not s2:
            return len(s1)
        prev = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            curr = [i + 1]
            for j, c2 in enumerate(s2):
                curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
            prev = curr
        return prev[-1]

from data.dominios_legitimos import DOMINIOS_LEGITIMOS

# Umbral de similitud: si similaridad >= este valor Y no es exacto → sospechoso
SIMILARITY_THRESHOLD = 0.70


def _extract_domain(url: str) -> str:
    """
    Extrae el dominio de una URL.
    Si no tiene esquema, agrega https:// para que urlparse funcione.

    Ejemplos:
        "https://bcp-descuentos.com/oferta" → "bcp-descuentos.com"
        "bcp.com.pe"                        → "bcp.com.pe"
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Eliminar "www."
    if domain.startswith("www."):
        domain = domain[4:]

    # Eliminar puerto si existe
    domain = domain.split(":")[0]

    return domain


def _strip_tld(domain: str) -> str:
    """
    Extrae la parte principal del dominio eliminando TLD conocidos.

    Ejemplos:
        "bcp.com.pe"    → "bcp"
        "sunat.gob.pe"  → "sunat"
        "bbva.pe"       → "bbva"
        "bcp-descuentos.com" → "bcp-descuentos"
    """
    known_tlds = (
        ".com.pe", ".gob.pe", ".edu.pe", ".org.pe", ".net.pe",
        ".com", ".net", ".org", ".pe", ".info", ".co",
    )
    d = domain.lower()
    for tld in sorted(known_tlds, key=len, reverse=True):  # más largos primero
        if d.endswith(tld):
            return d[: -len(tld)]
    # Si no coincide, devolver hasta el primer punto
    return d.split(".")[0]


def _compute_similarity(domain: str, reference: str) -> float:
    """
    Calcula la similitud entre dos dominios usando múltiples estrategias:

    1. Similitud Levenshtein del dominio completo
    2. Similitud Levenshtein del nombre sin TLD
    3. Bonus si el nombre del dominio malicioso EMPIEZA por el nombre legítimo
       (ej: "bcp-descuentos" empieza con "bcp" → alta sospecha)

    Retorna el valor máximo de las estrategias.
    Rango: 0.0 (completamente diferente) a 1.0 (idéntico).
    """
    def _lev_sim(a: str, b: str) -> float:
        max_len = max(len(a), len(b))
        if max_len == 0:
            return 1.0
        return round(1.0 - levenshtein_distance(a, b) / max_len, 4)

    # Estrategia 1: dominio completo
    sim_full = _lev_sim(domain, reference)

    # Estrategia 2: nombre sin TLD
    name_a = _strip_tld(domain)
    name_b = _strip_tld(reference)
    sim_name = _lev_sim(name_a, name_b)

    # Estrategia 3: prefijo — si el nombre legítimo es prefijo del sospechoso
    # Ejemplos: "bcp" en "bcp-descuentos", "bbva" en "bbva-peru", "sunat" en "sunat-afp"
    prefix_score = 0.0
    if len(name_b) >= 3 and (
        name_a.startswith(name_b)
        or name_a.startswith(name_b + "-")
        or name_a.startswith(name_b + ".")
    ):
        # Penalizar según cuánto "extra" tiene el dominio sospechoso
        extra_ratio = len(name_b) / len(name_a) if len(name_a) > 0 else 0
        prefix_score = 0.65 + (extra_ratio * 0.25)  # rango aprox. 0.65–0.90

    return max(sim_full, sim_name, prefix_score)


def _map_risk_level(is_suspicious: bool, similarity: float) -> str:
    """Mapea la sospecha y similitud a un nivel de riesgo."""
    if not is_suspicious:
        return "bajo"
    if similarity >= 0.85:
        return "alto"
    elif similarity >= 0.70:
        return "medio"
    return "bajo"


def analyze_url(url: str) -> dict:
    """
    Analiza una URL y detecta si es un intento de typosquatting
    contra algún dominio legítimo peruano conocido.

    Args:
        url: URL o dominio a analizar.

    Returns:
        dict con claves:
            - original_url: la URL original
            - extracted_domain: dominio extraído
            - is_suspicious: bool
            - closest_domain: dominio legítimo más parecido
            - similarity: float 0–1
            - risk_level: "alto", "medio" o "bajo"
            - source: "levenshtein"
    """
    if not url or not url.strip():
        return {
            "original_url": url,
            "extracted_domain": "",
            "is_suspicious": False,
            "closest_domain": None,
            "similarity": 0.0,
            "risk_level": "bajo",
            "source": "levenshtein",
            "error": "URL vacía",
        }

    domain = _extract_domain(url)

    if not domain:
        return {
            "original_url": url,
            "extracted_domain": domain,
            "is_suspicious": False,
            "closest_domain": None,
            "similarity": 0.0,
            "risk_level": "bajo",
            "source": "levenshtein",
            "error": "No se pudo extraer el dominio",
        }

    # Comparar contra todos los dominios legítimos
    best_similarity = 0.0
    best_match = None

    for legit in DOMINIOS_LEGITIMOS:
        sim = _compute_similarity(domain, legit)
        if sim > best_similarity:
            best_similarity = sim
            best_match = legit

    # Es sospechoso si la similitud es alta PERO el dominio NO es exactamente igual
    is_exact_match = domain == best_match
    is_suspicious = (not is_exact_match) and (best_similarity >= SIMILARITY_THRESHOLD)

    risk_level = _map_risk_level(is_suspicious, best_similarity)

    return {
        "original_url": url,
        "extracted_domain": domain,
        "is_suspicious": is_suspicious,
        "closest_domain": best_match,
        "similarity": best_similarity,
        "risk_level": risk_level,
        "source": "levenshtein",
    }
