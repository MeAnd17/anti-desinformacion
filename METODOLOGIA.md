# Capítulo de Metodología — Sistema Tucuy
## Detección de Desinformación Digital para Lima Metropolitana

---

## Contexto general del sistema

**Nombre del sistema:** Tucuy (del quechua: "todo", "completo")  
**Objetivo:** Detectar desinformación digital, enlaces fraudulentos y noticias falsas dirigidas a ciudadanos de Lima Metropolitana, con énfasis en adultos mayores y personas con baja alfabetización digital.  
**Canales de acceso:** Extensión de Chrome, Bot de WhatsApp, API REST  
**Backend:** FastAPI (Python) desplegado en Render — `https://tucuy-backend.onrender.com`  
**Modelo NLP base:** `Narrativaai/fake-news-detection-spanish` (RoBERTa-large fine-tuned, 77.97% accuracy)  
**Modelo NLP propio:** `analuciahm/tucuy-fake-news-spanish` (fine-tuned con corpus FakeDeS sobre PlanTL-GOB-ES/roberta-large-bne)  
**Modelo NLP producción:** `analuciahm/tucuy-fake-news-spanish-onnx` (cuantizado int8, 119MB, desplegado en Render free)  
**Fact-checking:** Google Fact Check Tools API + fallback DuckDuckGo  
**OCR:** OCR.space API  
**Detección de URLs:** Levenshtein + blacklist interna + Google Safe Browsing + URLhaus + OpenPhish + PhishTank  
**Bot de WhatsApp:** Baileys (`@whiskeysockets/baileys`) — sin Puppeteer, protocolo nativo  

---

## Arquitectura del sistema (capas)

```
┌─────────────────────────────────────────────────────────┐
│                CAPA DE PRESENTACIÓN                     │
│  Extensión Chrome      Bot WhatsApp      API directa    │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS REST
┌────────────────────────▼────────────────────────────────┐
│           API GATEWAY — FastAPI (Render)                │
│  /analyze/text  /analyze/url  /analyze/image            │
│  /analyze/full  /training/stats  /training/export       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              MÓDULOS DE ANÁLISIS                        │
│  nlp.py │ levenshtein.py │ ocr.py │ fact_check.py       │
│  url_checker.py │ formatter.py │ training_collector.py  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                 CAPA DE DATOS                           │
│  dominios_legitimos.py │ training.db (SQLite)           │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              SERVICIOS EXTERNOS                         │
│  Google Fact Check API │ Google Safe Browsing API       │
│  OCR.space API │ URLhaus (abuse.ch)                     │
│  OpenPhish (feed público) │ PhishTank                   │
└─────────────────────────────────────────────────────────┘
```

---

## Fase 1 — Análisis de texto (NLP)

### Descripción
Clasifica un texto en español como FAKE (desinformación) o REAL (legítimo) usando RoBERTa fine-tuned para español.

### Modelo
- **Base de referencia:** `Narrativaai/fake-news-detection-spanish` — baseline de comparación. Accuracy 77.97%, F1 77.17%.
- **Modelo propio:** `analuciahm/tucuy-fake-news-spanish` — entrenado desde `PlanTL-GOB-ES/roberta-large-bne` sobre corpus FakeDeS con hiperparámetros optimizados.
- **Modelo en producción:** `analuciahm/tucuy-fake-news-spanish-onnx` — versión ONNX cuantizada (int8). Pesa 119MB, carga con `onnxruntime` sin torch, cabe en los 512MB de RAM de Render free.
- **Dataset:** Spanish Fake News Corpus v1.0 (Posadas-Durán et al., 2019) — 676 noticias train, 295 test, balanceado 50/50.

### Limitación de despliegue resuelta
El modelo RoBERTa original (~500MB) excedía la RAM del plan gratuito de Render (512MB). Se resolvió convirtiendo el modelo a ONNX con cuantización int8, reduciendo el tamaño de 499MB a **119MB**.

### Estrategia de inferencia (2 niveles en cascada)

```
FUNCIÓN classify_text(texto):
    SI texto está vacío:
        RETORNAR {label: "REAL", confidence: 0.0, risk_level: "bajo"}

    // Nivel 1: modelo ONNX cuantizado (119MB, producción en Render)
    pipeline ← cargar_modelo_onnx("analuciahm/tucuy-fake-news-spanish-onnx")
    SI pipeline disponible:
        resultado ← pipeline(texto[:2000])
        RETORNAR {label, confidence, risk_level, inference: "onnx"}

    // Nivel 2: fallback heurístico por palabras clave
    RETORNAR fallback_heuristico(texto)
```

### Mapeo de confianza a nivel de riesgo

```
SI etiqueta == "FAKE":
    SI confianza > 0.85  → risk_level = "alto"
    SI confianza >= 0.60 → risk_level = "medio"
    SI confianza < 0.60  → risk_level = "bajo"
SINO:
    risk_level = "bajo"
```

---

## Fase 2 — Verificación de hechos (Fact-Check)

### Descripción
Verifica si una afirmación ha sido investigada por organizaciones periodísticas internacionales. El veredicto **eleva directamente el risk_level**:
- `FALSO` con confianza ≥ 0.70 → risk_level = "alto"
- `FALSO` con confianza < 0.70 → risk_level = "medio"

### Pseudocódigo

```
FUNCIÓN verify_claim(texto):
    SI GOOGLE_FACTCHECK_KEY configurada:
        resultado ← google_factcheck_api(texto, idioma="es")
        SI hay resultados:
            SI rating contiene ["falso", "false", "misleading"]:
                RETORNAR {veredicto: "FALSO", confianza: 0.85,
                          verificador, fuente, source: "google_factcheck"}
            SI rating contiene ["verdadero", "true", "correcto"]:
                RETORNAR {veredicto: "VERDADERO", confianza: 0.80}

    // Fallback: DuckDuckGo Instant Answer API (sin key)
    // puntúa keywords FALSO vs VERDADERO con peso doble para fuentes confiables
    RETORNAR {veredicto, confianza, source: "fact_check_ddg"}
```

---

## Fase 3 — Detección de URLs maliciosas

### Descripción
Detecta phishing, malware o typosquatting en tres niveles en cascada.

### Nivel 1 — Lista negra interna (~100 dominios)
Cubre phishing bancario peruano (BCP, BBVA, SUNAT, Yape), streaming pirata, y sitios de desinformación. Incluye detección por keywords para variantes con TLD diferente (ej: `cuevana3k.pro` → detectado por keyword "cuevana").

### Nivel 2 — Fuentes externas (4 APIs)
Google Safe Browsing, URLhaus, OpenPhish (feed público en caché), PhishTank. Opera con degradación elegante si alguna clave no está configurada.

### Nivel 3 — Similitud Levenshtein (~45 dominios legítimos peruanos)

```
PARA cada dominio_legitimo en DOMINIOS_LEGITIMOS:
    sim ← max(
        similitud_levenshtein(dominio, dominio_legitimo),
        similitud_levenshtein(sin_tld(dominio), sin_tld(dominio_legitimo)),
        bonus_prefijo(dominio, dominio_legitimo)
            // "bcp" prefijo de "bcp-descuentos" → score 0.65–0.90
    )

SI mejor_similitud >= 0.85 → risk_level = "alto"
SI mejor_similitud >= 0.70 → risk_level = "medio"
SINO                       → risk_level = "bajo"
```

---

## Fase 4 — OCR (análisis de imágenes)

### Descripción
Extrae texto de imágenes usando OCR.space API. Migración desde Tesseract local eliminó dependencias de binarios del SO, habilitando el despliegue en Render.

```
FUNCIÓN extract_text_from_image(imagen_bytes):
    respuesta ← POST https://api.ocr.space/parse/image
        {language: "spa", OCREngine: 2, scale: true, detectOrientation: true}

    texto    ← respuesta.ParsedResults[0].ParsedText
    has_text ← len(texto sin espacios) >= 10
    urls     ← detectar_urls_regex(texto)

    RETORNAR {extracted_text, has_text, confidence, urls_found}
```

---

## Fase 5 — Orquestador principal (/analyze/full)

Endpoint principal usado por el bot de WhatsApp y la extensión de Chrome. Ejecuta todos los módulos según el contenido recibido (texto, URL, imagen) y agrega el resultado con el nivel de riesgo más alto encontrado.

---

## Fase 6 — Retroalimentación automática

Cuando Google Fact Check devuelve un veredicto confiable (confianza ≥ 0.80, veredicto FALSO o VERDADERO), el texto se guarda automáticamente en SQLite como muestra de entrenamiento. Las etiquetas provienen de fact-checkers internacionales (Newtral, ColombiaCheck, AFP Factual, BBC Verify), no de usuarios — eliminando el riesgo de envenenamiento del dataset. Deduplicación por SHA-256.

---

## Flujos de los canales de acceso

### Bot de WhatsApp (Baileys — protocolo nativo)

El bot usa `@whiskeysockets/baileys` en lugar de `whatsapp-web.js`. La migración eliminó la dependencia de Puppeteer/Chromium, resolviendo el error `downloadMedia()` presente en `whatsapp-web.js` 1.34.7 con Node.js v24.

**Flujo conversacional con estado por usuario:**

```
Usuario escribe "hola"
    ↓
Tucuy se presenta y muestra menú:
    1️⃣ Enlace o URL
    2️⃣ Texto o frase
    3️⃣ Imagen o captura
    ↓
Usuario elige opción (1, 2 o 3)
    ↓ (opción inválida → pide elegir de nuevo)
Tucuy pide el contenido específico
    ↓
Usuario envía el contenido
    ↓
Tucuy llama al backend (Render):
    opción 1 → POST /analyze/url
    opción 2 → POST /analyze/text
    opción 3 → downloadMediaMessage() → POST /analyze/image (multipart)
    ↓
Tucuy responde con el análisis formateado
    ↓
"¿Querés verificar otro contenido? Respondé *sí* o *no*"
    ├── sí → vuelve al menú
    └── no → despedida, estado se resetea
                ↓
        Para volver → escribir "hola"
```

**Solo responde mensajes directos** (ignora grupos, estados y broadcasts).

### Extensión de Chrome (Manifest V3)

```
Al cargar cualquier página web
    ↓
content.js recolecta todos los <a href> HTTP/HTTPS
    ↓
background.js analiza en grupos de 5 — POST /analyze/url × N
    ↓
riesgo alto  → outline rojo + badge ⚠️ + tooltip al hover
riesgo medio → outline naranja + badge 🟡 + tooltip al hover
MutationObserver detecta cambios DOM (SPAs: Facebook, Twitter)

Popup (4 tabs): Texto | Enlace | Imagen | Todo
    ↓
POST /analyze/text, /analyze/url, /analyze/full
    ↓
Resultado con nivel de riesgo y mensaje formateado
```

---

## Estado del despliegue en producción

| Componente | Estado | Notas |
|---|---|---|
| Backend FastAPI | ✅ Activo | `https://tucuy-backend.onrender.com` |
| Modelo NLP ONNX (119MB) | ✅ Funcionando en Render | `analuciahm/tucuy-fake-news-spanish-onnx` |
| Google Fact Check | ✅ Funcionando | Veredictos elevan risk_level |
| Google Safe Browsing | ✅ Funcionando | Detecta MALWARE, PHISHING |
| OCR.space | ✅ Funcionando | Extracción de texto en español |
| Levenshtein + Blacklist | ✅ Funcionando | Dominio peruano específico |
| OpenPhish | ✅ Funcionando | Feed público, sin API key |
| Extensión Chrome | ✅ Activa | Apunta a Render |
| Bot WhatsApp (Baileys) | ✅ Funcional | Requiere correr `node index.js` localmente |

---

## Estructura de archivos del proyecto

```
anti-desinformacion/
├── backend/
│   ├── main.py                       # API FastAPI — endpoints de análisis
│   ├── modules/
│   │   ├── nlp.py                    # ONNX + fallback heurístico
│   │   ├── levenshtein.py            # Typosquatting + blacklist
│   │   ├── ocr.py                    # OCR via OCR.space API
│   │   ├── fact_check.py             # Google Fact Check + DuckDuckGo
│   │   ├── url_checker.py            # GSB + URLhaus + OpenPhish + PhishTank
│   │   ├── formatter.py              # Mensajes diferenciados por canal
│   │   └── training_collector.py     # Recolección automática de muestras
│   ├── data/
│   │   └── dominios_legitimos.py     # Listas blanca (~45) y negra (~100)
│   ├── Procfile                      # Comando arranque Render
│   ├── .python-version               # Python 3.11
│   └── requirements.txt
├── extension/
│   ├── background.js                 # Service worker (Manifest V3)
│   ├── content.js                    # Escaneo DOM + tooltips + overlay
│   ├── popup.html / popup.js         # UI 4 tabs
│   └── manifest.json                 # Apunta a tucuy-backend.onrender.com
├── whatsapp-bot/
│   ├── index.js                      # Bot Baileys con flujo conversacional
│   └── api_client.js                 # Axios client — apunta a Render (2min timeout)
└── docs/
    └── privacy-policy.html           # Política de privacidad
```

---

## Variables de entorno del sistema

| Variable | Servicio | Estado |
|---|---|---|
| `GOOGLE_FACTCHECK_KEY` | Google Fact Check Tools API | ✅ Configurada |
| `GOOGLE_SAFE_BROWSING_KEY` | Google Safe Browsing v4 | ✅ Configurada |
| `OCR_SPACE_KEY` | OCR.space API | ✅ Configurada |
| `HF_TOKEN` | Hugging Face | ✅ Configurada |
| `URLHAUS_AUTH_KEY` | URLhaus / abuse.ch | Pendiente |
| `PHISHTANK_APP_KEY` | PhishTank | Opcional |

---

## Decisiones de diseño relevantes

1. **Modelo NLP propio con despliegue optimizado**: entrenado desde `PlanTL-GOB-ES/roberta-large-bne` sobre FakeDeS, convertido a ONNX int8 (499MB → 119MB) para caber en Render free (512MB RAM).

2. **Migración a Baileys**: `whatsapp-web.js` 1.34.7 presenta un bug crítico en `downloadMedia()` con Node.js v24 (error en Puppeteer `ExecutionContext`). Baileys usa el protocolo nativo de WhatsApp sin Puppeteer, resolviendo el problema completamente.

3. **Flujo conversacional con estado**: el bot mantiene el estado de cada usuario en memoria (opción elegida, esperando contenido, esperando confirmación de continuación). Esto permite una experiencia guiada y sin ambigüedades.

4. **Retroalimentación sin intervención humana**: etiquetas de entrenamiento provenientes de fact-checkers internacionales, no de usuarios. Elimina riesgo de envenenamiento del dataset.

5. **Degradación elegante**: el sistema nunca falla completamente. Si el modelo NLP no está disponible, usa heurística. Si una API externa falla, se omite. Si el fact-check no tiene resultados, retorna INCIERTO.

6. **Riesgo máximo como agregador**: cuando hay señales de múltiples módulos, se reporta el nivel más alto (principio de precaución).

7. **Contexto peruano explícito**: blacklist y dominios legítimos construidos para el ecosistema digital peruano (BCP, BBVA, Interbank, SUNAT, RENIEC, MINSA, Yape, Plin, El Comercio, RPP, Andina).

8. **Canal-aware formatting**: WhatsApp recibe markdown con lenguaje coloquial para adultos mayores; la extensión Chrome recibe texto plano conciso para uso en escritorio.
