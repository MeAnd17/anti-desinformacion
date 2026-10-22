"""
Módulo Training Collector — Recolección automática de muestras de entrenamiento.

Camino A: Automatización directa con Google Fact Check.

Cada vez que el sistema analiza un texto y Google Fact Check devuelve un
veredicto confiable (FALSO o VERDADERO con confianza >= 0.80), ese texto
se guarda automáticamente como muestra de entrenamiento.

La etiqueta proviene de organizaciones periodísticas internacionales
(ColombiaCheck, AFP Factual, BBC, etc.), no de usuarios, eliminando
el riesgo de datos maliciosos o incorrectos.

Los datos se guardan en SQLite (backend/data/training.db).
No se almacena ningún dato del usuario — solo el texto limpio y la etiqueta.
"""

from __future__ import annotations

import sqlite3
import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent.parent / "data" / "training.db"

# Umbrales de calidad para aceptar una muestra
MIN_CONFIDENCE     = 0.80   # confianza mínima del veredicto de Google Fact Check
MIN_TEXT_LENGTH    = 20     # caracteres mínimos del texto
MAX_TEXT_LENGTH    = 2000   # caracteres máximos
VALID_VERDICTS     = {"FALSO", "VERDADERO"}  # no guardar INCIERTO


# ---------------------------------------------------------------------------
# Inicialización de la base de datos
# ---------------------------------------------------------------------------

def _get_connection() -> sqlite3.Connection:
    """Retorna una conexión a la base de datos SQLite."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Crea la tabla de muestras de entrenamiento si no existe.
    Llamar una vez al iniciar el backend.
    """
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_samples (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                text_hash   TEXT UNIQUE,          -- hash SHA256 del texto (evita duplicados)
                text        TEXT NOT NULL,         -- texto limpio sin datos del usuario
                label       TEXT NOT NULL,         -- FAKE o REAL
                veredicto   TEXT NOT NULL,         -- FALSO o VERDADERO (de Google FC)
                confianza   REAL NOT NULL,         -- confianza del veredicto (0-1)
                fuente      TEXT,                  -- URL de la verificación original
                verificador TEXT,                  -- nombre del medio verificador
                resumen     TEXT,                  -- resumen del fact-check
                created_at  TEXT NOT NULL          -- timestamp ISO
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_label ON training_samples(label)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_created ON training_samples(created_at)
        """)
        conn.commit()
    logger.info(f"[Collector] Base de datos inicializada en {DB_PATH}")


# ---------------------------------------------------------------------------
# Función principal de recolección
# ---------------------------------------------------------------------------

def try_collect_sample(text: str, fact_check_result: dict) -> bool:
    """
    Intenta guardar un texto como muestra de entrenamiento.

    Solo guarda si se cumplen TODAS las condiciones de calidad:
      1. La fuente es Google Fact Check (no DuckDuckGo fallback)
      2. El veredicto es FALSO o VERDADERO (no INCIERTO)
      3. La confianza es >= MIN_CONFIDENCE (0.80)
      4. El texto tiene longitud adecuada

    Args:
        text: Texto analizado (ya limpio, sin datos del usuario).
        fact_check_result: Dict retornado por verify_claim().

    Returns:
        True si la muestra fue guardada, False si fue descartada.
    """
    # --- Validaciones de calidad ---

    if not text or not text.strip():
        return False

    text = text.strip()

    # Longitud adecuada
    if not (MIN_TEXT_LENGTH <= len(text) <= MAX_TEXT_LENGTH):
        return False

    # Debe venir de Google Fact Check, no del fallback
    if fact_check_result.get("source") != "google_factcheck":
        return False

    veredicto = fact_check_result.get("veredicto", "")
    if veredicto not in VALID_VERDICTS:
        return False

    confianza = fact_check_result.get("confianza", 0.0)
    if confianza < MIN_CONFIDENCE:
        return False

    # --- Mapear veredicto a etiqueta del modelo ---
    label = "FAKE" if veredicto == "FALSO" else "REAL"

    # --- Deduplicación por hash ---
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # --- Extraer nombre del verificador ---
    resumen = fact_check_result.get("resumen", "") or ""
    verificador = ""
    if "(" in resumen and resumen.endswith(")"):
        verificador = resumen[resumen.rfind("(") + 1:-1].strip()

    resumen_limpio = resumen
    if " — Calificación" in resumen:
        resumen_limpio = resumen[:resumen.rfind(" — Calificación")]

    # --- Guardar en la base de datos ---
    try:
        with _get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO training_samples
                    (text_hash, text, label, veredicto, confianza, fuente, verificador, resumen, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                text_hash,
                text,
                label,
                veredicto,
                confianza,
                fact_check_result.get("fuente", ""),
                verificador,
                resumen_limpio[:300],
                datetime.utcnow().isoformat(),
            ))
            saved = conn.execute(
                "SELECT changes()"
            ).fetchone()[0]
            conn.commit()

        if saved:
            logger.info(
                f"[Collector] Muestra guardada: label={label}, "
                f"confianza={confianza}, verificador={verificador}, "
                f"texto='{text[:60]}...'"
            )
            return True
        else:
            logger.debug(f"[Collector] Muestra duplicada descartada: {text_hash[:16]}...")
            return False

    except Exception as e:
        logger.error(f"[Collector] Error al guardar muestra: {e}")
        return False


# ---------------------------------------------------------------------------
# Consultas útiles
# ---------------------------------------------------------------------------

def get_stats() -> dict:
    """Retorna estadísticas del dataset acumulado."""
    try:
        with _get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM training_samples").fetchone()[0]
            fake  = conn.execute("SELECT COUNT(*) FROM training_samples WHERE label='FAKE'").fetchone()[0]
            real  = conn.execute("SELECT COUNT(*) FROM training_samples WHERE label='REAL'").fetchone()[0]
            verificadores = conn.execute("""
                SELECT verificador, COUNT(*) as n
                FROM training_samples
                WHERE verificador != ''
                GROUP BY verificador
                ORDER BY n DESC
                LIMIT 10
            """).fetchall()

        return {
            "total": total,
            "fake": fake,
            "real": real,
            "verificadores": [{"nombre": r["verificador"], "muestras": r["n"]} for r in verificadores],
        }
    except Exception as e:
        logger.error(f"[Collector] Error al obtener stats: {e}")
        return {"total": 0, "fake": 0, "real": 0, "verificadores": []}


def export_dataset(output_path: str | None = None) -> str:
    """
    Exporta el dataset acumulado como archivo JSONL listo para fine-tuning.

    Formato de cada línea:
        {"text": "...", "label": "FAKE"}  o  {"label": "REAL"}

    Returns:
        Ruta del archivo generado.
    """
    import json

    if output_path is None:
        output_path = str(Path(__file__).parent.parent / "data" / "training_dataset.jsonl")

    try:
        with _get_connection() as conn:
            rows = conn.execute(
                "SELECT text, label, veredicto, confianza, verificador FROM training_samples ORDER BY created_at"
            ).fetchall()

        with open(output_path, "w", encoding="utf-8") as f:
            for row in rows:
                entry = {
                    "text":        row["text"],
                    "label":       row["label"],
                    "veredicto":   row["veredicto"],
                    "confianza":   row["confianza"],
                    "verificador": row["verificador"],
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(f"[Collector] Dataset exportado: {len(rows)} muestras → {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"[Collector] Error al exportar: {e}")
        raise
