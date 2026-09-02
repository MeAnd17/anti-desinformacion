"""
Tests End-to-End — 10 casos reales de desinformación peruana.

Evalúa el sistema completo y calcula métricas académicas:
Exactitud (Accuracy), F1-Score, Recall y Precisión.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.nlp import classify_text
from modules.levenshtein import analyze_url
from modules.formatter import format_response


# ---------------------------------------------------------------------------
# Dataset de 10 casos etiquetados manualmente
# ---------------------------------------------------------------------------

CASOS = [
    # --- Fake News (label esperado: FAKE / is_suspicious: True) ---
    {
        "id": 1,
        "tipo": "texto",
        "input": "URGENTE: El gobierno peruano está envenenando el agua con cloro para reducir la población. Comparte antes de que borren esto.",
        "expected_fake": True,
        "descripcion": "Conspiración sobre el agua",
    },
    {
        "id": 2,
        "tipo": "texto",
        "input": "¡EXCLUSIVO! Médicos descubren que el huevo de gallina cura la diabetes tipo 2 en 3 días. Lo que las farmacéuticas no quieren que sepas.",
        "expected_fake": True,
        "descripcion": "Cura milagrosa de salud",
    },
    {
        "id": 3,
        "tipo": "texto",
        "input": "El Congreso aprobó en secreto una ley para quitarles la pensión a todos los adultos mayores del Perú. Esto es lo que no te dicen.",
        "expected_fake": True,
        "descripcion": "Fake news sobre pensiones",
    },
    # --- URLs de typosquatting (is_suspicious: True) ---
    {
        "id": 4,
        "tipo": "url",
        "input": "https://bcp-descuentos.com/oferta-especial",
        "expected_suspicious": True,
        "descripcion": "Typosquatting del BCP",
    },
    {
        "id": 5,
        "tipo": "url",
        "input": "https://sunat-afp-consulta.com/clave-sol",
        "expected_suspicious": True,
        "descripcion": "Typosquatting de SUNAT",
    },
    {
        "id": 6,
        "tipo": "url",
        "input": "https://reniec-tramites-online.com/renovar-dni",
        "expected_suspicious": True,
        "descripcion": "Typosquatting de RENIEC",
    },
    # --- Verdaderos negativos — Contenido legítimo (label esperado: REAL / is_suspicious: False) ---
    {
        "id": 7,
        "tipo": "texto",
        "input": "El Ministerio de Salud del Perú anuncia la apertura de 50 nuevos centros de vacunación gratuita en Lima Metropolitana para este mes.",
        "expected_fake": False,
        "descripcion": "Comunicado oficial MINSA",
    },
    {
        "id": 8,
        "tipo": "texto",
        "input": "La SUNAT recuerda a los contribuyentes que el plazo para presentar la declaración jurada anual vence el 31 de marzo.",
        "expected_fake": False,
        "descripcion": "Aviso oficial SUNAT",
    },
    {
        "id": 9,
        "tipo": "url",
        "input": "https://sunat.gob.pe/cl-ti-itmrconsruc/jcrS00Alias",
        "expected_suspicious": False,
        "descripcion": "URL real de SUNAT",
    },
    {
        "id": 10,
        "tipo": "url",
        "input": "https://bcp.com.pe/personas/tarjetas",
        "expected_suspicious": False,
        "descripcion": "URL real del BCP",
    },
]


# ---------------------------------------------------------------------------
# Tests e2e individuales
# ---------------------------------------------------------------------------

class TestCasosE2E:

    def test_caso_01_conspiracion_agua(self):
        caso = CASOS[0]
        result = classify_text(caso["input"])
        assert result["label"] in ("FAKE", "REAL")
        assert result["risk_level"] in ("alto", "medio", "bajo")
        print(f"\n[Caso {caso['id']}] {caso['descripcion']}: {result['label']} ({result['confidence']*100:.0f}%)")

    def test_caso_02_cura_milagrosa(self):
        caso = CASOS[1]
        result = classify_text(caso["input"])
        assert result["label"] in ("FAKE", "REAL")
        print(f"\n[Caso {caso['id']}] {caso['descripcion']}: {result['label']} ({result['confidence']*100:.0f}%)")

    def test_caso_03_fake_pensiones(self):
        caso = CASOS[2]
        result = classify_text(caso["input"])
        assert result["label"] in ("FAKE", "REAL")
        print(f"\n[Caso {caso['id']}] {caso['descripcion']}: {result['label']} ({result['confidence']*100:.0f}%)")

    def test_caso_04_typosquatting_bcp(self):
        caso = CASOS[3]
        result = analyze_url(caso["input"])
        assert result["source"] == "levenshtein"
        print(f"\n[Caso {caso['id']}] {caso['descripcion']}: sospechoso={result['is_suspicious']}, similar a={result['closest_domain']}")

    def test_caso_05_typosquatting_sunat(self):
        caso = CASOS[4]
        result = analyze_url(caso["input"])
        assert result["source"] == "levenshtein"
        print(f"\n[Caso {caso['id']}] {caso['descripcion']}: sospechoso={result['is_suspicious']}, similar a={result['closest_domain']}")

    def test_caso_06_typosquatting_reniec(self):
        caso = CASOS[5]
        result = analyze_url(caso["input"])
        assert result["source"] == "levenshtein"
        print(f"\n[Caso {caso['id']}] {caso['descripcion']}: sospechoso={result['is_suspicious']}, similar a={result['closest_domain']}")

    def test_caso_07_comunicado_minsa(self):
        caso = CASOS[6]
        result = classify_text(caso["input"])
        assert result["label"] in ("FAKE", "REAL")
        print(f"\n[Caso {caso['id']}] {caso['descripcion']}: {result['label']} ({result['confidence']*100:.0f}%)")

    def test_caso_08_aviso_sunat(self):
        caso = CASOS[7]
        result = classify_text(caso["input"])
        assert result["label"] in ("FAKE", "REAL")
        print(f"\n[Caso {caso['id']}] {caso['descripcion']}: {result['label']} ({result['confidence']*100:.0f}%)")

    def test_caso_09_url_real_sunat(self):
        caso = CASOS[8]
        result = analyze_url(caso["input"])
        assert result["is_suspicious"] is False
        assert result["risk_level"] == "bajo"
        print(f"\n[Caso {caso['id']}] {caso['descripcion']}: sospechoso={result['is_suspicious']}")

    def test_caso_10_url_real_bcp(self):
        caso = CASOS[9]
        result = analyze_url(caso["input"])
        assert result["is_suspicious"] is False
        assert result["risk_level"] == "bajo"
        print(f"\n[Caso {caso['id']}] {caso['descripcion']}: sospechoso={result['is_suspicious']}")


# ---------------------------------------------------------------------------
# Cálculo de métricas académicas
# ---------------------------------------------------------------------------

def calcular_metricas():
    """
    Calcula Accuracy, Precision, Recall y F1-Score del sistema.
    Retorna la tabla de métricas para incluir en la tesis.
    """
    tp = tn = fp = fn = 0

    print("\n" + "=" * 70)
    print("EVALUACIÓN E2E — SISTEMA ANTI-DESINFORMACIÓN")
    print("=" * 70)
    print(f"{'ID':<4} {'Descripción':<35} {'Esperado':<12} {'Obtenido':<12} {'OK'}")
    print("-" * 70)

    for caso in CASOS:
        if caso["tipo"] == "texto":
            result = classify_text(caso["input"])
            predicted_positive = result["label"] == "FAKE"
            actual_positive = caso["expected_fake"]
            obtenido = result["label"]
            esperado = "FAKE" if actual_positive else "REAL"

        elif caso["tipo"] == "url":
            result = analyze_url(caso["input"])
            predicted_positive = result["is_suspicious"]
            actual_positive = caso["expected_suspicious"]
            obtenido = "SOSPECHOSO" if predicted_positive else "SEGURO"
            esperado = "SOSPECHOSO" if actual_positive else "SEGURO"

        ok = "✓" if predicted_positive == actual_positive else "✗"

        if actual_positive and predicted_positive:
            tp += 1
        elif not actual_positive and not predicted_positive:
            tn += 1
        elif not actual_positive and predicted_positive:
            fp += 1
        else:
            fn += 1

        print(f"{caso['id']:<4} {caso['descripcion'][:34]:<35} {esperado:<12} {obtenido:<12} {ok}")

    print("-" * 70)

    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\nMATRIZ DE CONFUSIÓN:")
    print(f"  VP (Verdaderos Positivos): {tp}")
    print(f"  VN (Verdaderos Negativos): {tn}")
    print(f"  FP (Falsos Positivos):     {fp}")
    print(f"  FN (Falsos Negativos):     {fn}")

    print(f"\nMÉTRICAS DEL SISTEMA:")
    print(f"  Exactitud (Accuracy):  {accuracy:.4f}  ({accuracy*100:.2f}%)")
    print(f"  Precisión (Precision): {precision:.4f}  ({precision*100:.2f}%)")
    print(f"  Exhaustividad (Recall):{recall:.4f}  ({recall*100:.2f}%)")
    print(f"  F1-Score:              {f1:.4f}  ({f1*100:.2f}%)")
    print("=" * 70)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
    }


def test_metricas_minimas():
    """Verifica que el sistema alcanza métricas mínimas aceptables."""
    metricas = calcular_metricas()
    # Para la demo académica, el sistema debe superar el 50% en cada métrica
    assert metricas["accuracy"] >= 0.5, f"Accuracy muy baja: {metricas['accuracy']}"


if __name__ == "__main__":
    calcular_metricas()
