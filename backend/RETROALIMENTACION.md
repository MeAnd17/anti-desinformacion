# Retroalimentación Automática del Modelo — Camino A

## ¿Qué es?

Cada vez que un usuario analiza un texto, el sistema consulta a Google Fact Check Tools API. Si esa API devuelve un veredicto confiable (verificado por un medio periodístico), el texto se guarda automáticamente como muestra de entrenamiento.

El modelo se nutre solo, sin intervención humana y sin riesgo de datos falsos.

---

## ¿Por qué es confiable?

La etiqueta no viene del usuario. Viene de organizaciones como **ColombiaCheck**, **AFP Factual**, **BBC Verify**, **Snopes** u otras que ya investigaron esa afirmación con rigor periodístico. Google Fact Check es simplemente el índice que agrupa esas verificaciones.

---

## Condiciones para guardar una muestra

Se guardan **solo** los textos que cumplen las tres condiciones a la vez:

| Condición | Valor |
|---|---|
| Fuente del veredicto | Google Fact Check (no el fallback DuckDuckGo) |
| Veredicto | Solo `FALSO` o `VERDADERO` — nunca `INCIERTO` |
| Confianza | ≥ 0.80 (80%) |
| Longitud del texto | Entre 20 y 2000 caracteres |

Si alguna falla, el texto se descarta silenciosamente.

---

## ¿Qué se guarda exactamente?

Solo el texto limpio y su etiqueta. Nada del usuario.

```
texto       → "El 5G causa coronavirus"
label       → FAKE
veredicto   → FALSO
confianza   → 0.85
verificador → ColombiaCheck
fuente      → https://colombiacheck.com/...
resumen     → "De nuevo, la tecnología 5G no es la causante del COVID-19"
```

Se usa un hash SHA-256 del texto para evitar duplicados. Si la misma afirmación llega 100 veces, se guarda una sola vez.

---

## Arquitectura del componente

```
Usuario envía texto
        ↓
  /analyze/text  o  /analyze/full
        ↓
  verify_claim()  →  Google Fact Check API
        ↓
  ¿veredicto confiable?
     ├── NO  → descartado (silencioso)
     └── SÍ  → try_collect_sample()
                      ↓
               data/training.db  (SQLite)
```

---

## Archivos involucrados

| Archivo | Rol |
|---|---|
| `modules/training_collector.py` | Lógica de recolección, deduplicación y exportación |
| `data/training.db` | Base de datos SQLite con las muestras acumuladas |
| `data/training_dataset.jsonl` | Dataset exportado listo para fine-tuning |
| `main.py` | Llama a `try_collect_sample()` en los endpoints de texto |

---

## Endpoints disponibles

### Ver estadísticas del dataset
```
GET /training/stats
```
Respuesta:
```json
{
  "total": 47,
  "fake": 39,
  "real": 8,
  "verificadores": [
    { "nombre": "ColombiaCheck", "muestras": 21 },
    { "nombre": "AFP Factual",   "muestras": 14 }
  ]
}
```

### Exportar dataset para fine-tuning
```
POST /training/export
```
Genera `data/training_dataset.jsonl` con una muestra por línea:
```jsonl
{"text": "El 5G causa coronavirus", "label": "FAKE", "veredicto": "FALSO", "confianza": 0.85, "verificador": "ColombiaCheck"}
{"text": "...", "label": "REAL", ...}
```

---

## Limitación conocida

Google Fact Check tiene mayor cobertura de desinformación global en español (microchips, 5G, COVID) que de desinformación local peruana (Yape, SUNAT, eventos políticos nacionales). Para complementar esto, se puede agregar un scraper de `verificador.larepublica.pe` como fuente adicional de etiquetas.

---

## Próximo paso: fine-tuning

Cuando el dataset tenga suficientes muestras (recomendado: ≥ 200 por clase), se puede hacer fine-tuning del modelo RoBERTa actual con:

```bash
python scripts/finetune.py --dataset data/training_dataset.jsonl
```

Esto reemplaza el modelo base con uno adaptado al contexto peruano.
