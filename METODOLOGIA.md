# Capítulo de Metodología — Sistema Tucuy
## Detección de Desinformación Digital para Lima Metropolitana

---

## Contexto general del sistema

**Nombre del sistema:** Tucuy (del quechua: "todo", "completo")  
**Objetivo:** Detectar desinformación digital, enlaces fraudulentos y noticias falsas dirigidas a ciudadanos de Lima Metropolitana, con énfasis en adultos mayores y personas con baja alfabetización digital.  
**Canales de acceso:** Extensión de Chrome (publicada en Chrome Web Store), Bot de WhatsApp, API REST  
**Backend:** FastAPI (Python) desplegado en Render — `https://tucuy-backend.onrender.com`  
**Modelo NLP base:** `Narrativaai/fake-news-detection-spanish` (RoBERTa-large fine-tuned, 77.97% accuracy)  
**Modelo NLP propio:** `analuciahm/tucuy-fake-news-spanish` (fine-tuned con corpus FakeDeS, en proceso de evaluación)  
**Fact-checking:** Google Fact Check Tools API + fallback DuckDuckGo  
**OCR:** OCR.space API  
**Detección de URLs:** Levenshtein + blacklist interna + Google Safe Browsing + URLhaus + OpenPhish + PhishTank  

---

## Arquitectura del sistema (capas)

```
┌─────────────────────────────────────────────────────────┐
│                CAPA DE PRESENTACIÓN                     │
│  Extensión Chrome (CWS)  Bot WhatsApp   API directa     │
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
│  Hugging Face (modelo NLP — solo entorno local)         │
└─────────────────────────────────────────────────────────┘
```

---

## Fase 1 — Análisis de texto (NLP)

### Descripción
Clasifica un texto en español como FAKE (desinformación) o REAL (legítimo) usando RoBERTa fine-tuned para español.

### Modelo
- **Base:** `Narrativaai/fake-news-detection-spanish` — RoBERTa-large-bne fine-tuned sobre el corpus FakeDeS (IberLEF 2021). Accuracy 77.97%, F1 77.17% sobre el set de evaluación.
- **Propio:** `analuciahm/tucuy-fake-news-spanish` — fine-tuning adicional sobre el mismo corpus con hiperparámetros optimizados para el contexto del sistema.
- **Dataset:** Spanish Fake News Corpus v1.0 (Posadas-Durán et al., 2019) — 676 noticias train, 295 test, balanceado 50/50 entre Fake y True, 9 categorías temáticas.

### Limitación de despliegue
El modelo RoBERTa (~500MB) excede la RAM disponible en el plan gratuito de Render (512MB). En producción el NLP opera con un **clasificador heurístico** basado en palabras clave mientras se implementa la conversión a ONNX (~130MB). El modelo completo funciona en entorno local.

### Trabajo futuro inmediato
Convertir el modelo fine-tuned a formato ONNX con cuantización int8, reduciendo el tamaño a ~130MB para desplegarlo en Render free sin overhead de torch ni transformers.

### Estrategia de inferencia (3 niveles en cascada)

```
FUNCIÓN classify_text(texto):
    SI texto está vacío:
        RETORNAR {label: "REAL", confidence: 0.0, risk_level: "bajo"}

    // Nivel 1: pipeline local con modelo RoBERTa (entorno local/GPU)
    pipeline ← cargar_modelo_roberta_local()
    SI pipeline disponible:
        resultado ← pipeline(texto[:2000])
        label     ← normalizar(resultado.label)
            // LABEL_1, 1, FAKE, FALSO → "FAKE" / resto → "REAL"
        confianza ← resultado.score
        RETORNAR {label, confidence, risk_level, inference: "local"}

    // Nivel 2: fallback heurístico (producción Render free)
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

### Fallback heurístico

```
FUNCIÓN fallback_heuristico(texto):
    KEYWORDS_FAKE = [
        "cura milagrosa", "el gobierno oculta",
        "comparte antes de que borren", "urgente",
        "ganaste", "premio", "murió", "murio",
        "vacuna mata", "5g causa", "no te vacunes", ...
    ]  // 25+ palabras clave de desinformación

    coincidencias ← contar keywords en texto.lower()

    SI coincidencias >= 3: RETORNAR {label: "FAKE", confidence: 0.78}
    SI coincidencias >= 1: RETORNAR {label: "FAKE", confidence: 0.62}
    SINO:                  RETORNAR {label: "REAL", confidence: 0.85}
```

---

## Fase 2 — Verificación de hechos (Fact-Check)

### Descripción
Verifica si una afirmación ha sido investigada por organizaciones periodísticas internacionales a través de la Google Fact Check Tools API. Es el módulo principal de detección en producción cuando el modelo NLP completo no está disponible.

### Integración con el nivel de riesgo
El veredicto del fact-check **eleva directamente el risk_level** del análisis:
- Si veredicto es `FALSO` con confianza ≥ 0.70 → risk_level = "alto"
- Si veredicto es `FALSO` con confianza < 0.70 → risk_level = "medio"
- Esto ocurre independientemente de lo que diga el NLP

### Pseudocódigo

```
FUNCIÓN verify_claim(texto):
    SI GOOGLE_FACTCHECK_KEY configurada:
        resultado ← google_factcheck_api(texto, idioma="es")

        SI hay resultados:
            rating      ← resultado.claimReview[0].textualRating
            verificador ← resultado.claimReview[0].publisher.name
            fuente      ← resultado.claimReview[0].url

            SI rating contiene ["falso", "false", "misleading"]:
                RETORNAR {veredicto: "FALSO", confianza: 0.85,
                          verificador, fuente, source: "google_factcheck"}

            SI rating contiene ["verdadero", "true", "correcto"]:
                RETORNAR {veredicto: "VERDADERO", confianza: 0.80,
                          source: "google_factcheck"}

    // Fallback: DuckDuckGo Instant Answer API (sin key)
    resultados ← duckduckgo_search(texto)
    // puntúa keywords FALSO vs VERDADERO
    // peso doble para fuentes confiables (andina.pe, rpp.pe, bbc.com)
    RETORNAR {veredicto, confianza, source: "fact_check_ddg"}
```

### Mensaje al usuario cuando hay fact-check confiable

```
• ❌ Verificación: FALSO (85% confianza) — verificado por Newtral
  "El bulo de las falsas muertes por vacunas covid en Nueva Zelanda"
  🔗 https://newtral.es/...
```

---

## Fase 3 — Detección de URLs maliciosas

### Descripción
Detecta si una URL es phishing, malware o typosquatting. Usa tres niveles en cascada, cada uno puede cortocircuitar el siguiente.

### Nivel 1 — Lista negra interna (~100 dominios)

```
FUNCIÓN check_blacklist(dominio):
    // Categorías: phishing bancario peruano (BCP, BBVA, SUNAT, Yape...),
    // streaming pirata, casinos no regulados en Perú, malware/adware,
    // sitios de desinformación documentados

    // Estrategia 1: dominio exacto y subdominios
    PARA cada sufijo en partes del dominio:
        SI sufijo en DOMINIOS_BLACKLIST:
            RETORNAR {match: sufijo, reason: BLACKLIST_REASONS[sufijo]}

    // Estrategia 2: keywords para variantes con TLD diferente
    // Ej: cuevana3k.pro contiene "cuevana" → detectado
    dominio_limpio ← dominio.replace("-", "").replace(".", "")
    PARA cada keyword en KEYWORD_RULES:
        SI keyword en dominio_limpio:
            RETORNAR {match: dominio, reason: KEYWORD_RULES[keyword]}

    RETORNAR null
```

### Nivel 2 — Fuentes externas (4 APIs)

```
FUNCIÓN check_url_external(url):
    // Degradación elegante: omite fuentes sin API key configurada
    resultados += google_safe_browsing(url)
        // MALWARE, SOCIAL_ENGINEERING, UNWANTED_SOFTWARE
    resultados += urlhaus_abusedb(url)
        // malware activo en tiempo real
    resultados += openphish_feed(url)
        // caché local descargado de feed público, TTL 1 hora
    resultados += phishtank(url)
        // base de datos comunitaria de phishing

    SI alguno detectó amenaza:
        RETORNAR {is_malicious: true, risk_level: "alto",
                  detections: [...], sources_checked: [...]}
    RETORNAR {is_malicious: false}
```

### Nivel 3 — Similitud Levenshtein (~45 dominios legítimos peruanos)

```
FUNCIÓN analyze_url(url):
    dominio ← extraer_dominio(url)  // quita https://, www., puerto

    SI check_blacklist(dominio):
        RETORNAR {source: "blacklist", risk_level: "alto"}

    SI check_url_external(url).is_malicious:
        RETORNAR {source: "external", risk_level: "alto"}

    // Comparar contra dominios legítimos peruanos:
    // bancos (BCP, BBVA, Interbank, Scotiabank, BN),
    // gobierno (SUNAT, RENIEC, MINSA, MEF, PCM),
    // medios (El Comercio, RPP, Andina, La República),
    // servicios (Yape, Plin, MercadoLibre, Google, Facebook)

    PARA cada dominio_legitimo en DOMINIOS_LEGITIMOS:
        sim ← max(
            similitud_levenshtein(dominio, dominio_legitimo),
            similitud_levenshtein(sin_tld(dominio), sin_tld(dominio_legitimo)),
            bonus_prefijo(dominio, dominio_legitimo)
                // "bcp" es prefijo de "bcp-descuentos" → score 0.65–0.90
        )

    SI mejor_similitud >= 0.85 → risk_level = "alto"
    SI mejor_similitud >= 0.70 → risk_level = "medio"
    SINO                       → risk_level = "bajo"

    RETORNAR {is_suspicious, closest_domain, similarity, risk_level,
              source: "levenshtein"}
```

---

## Fase 4 — OCR (análisis de imágenes)

### Descripción
Extrae el texto visible de una imagen usando OCR.space API. La migración desde Tesseract local eliminó la dependencia de binarios del sistema operativo, habilitando el despliegue en Render.

### Pseudocódigo

```
FUNCIÓN extract_text_from_image(imagen_bytes):
    image_b64  ← base64.encode(imagen_bytes)
    mime_type  ← detectar_mime(imagen_bytes)  // por magic bytes

    respuesta ← POST https://api.ocr.space/parse/image
        headers: {apikey: OCR_SPACE_KEY}
        body: {
            base64image: "data:{mime_type};base64,{image_b64}",
            language: "spa",        // español
            OCREngine: 2,           // motor LSTM más preciso
            scale: true,            // mejora imágenes pequeñas
            detectOrientation: true
        }

    texto    ← respuesta.ParsedResults[0].ParsedText
    has_text ← len(texto sin espacios) >= 10
    urls     ← detectar_urls_regex(texto)

    RETORNAR {extracted_text, has_text, confidence, urls_found}
```

---

## Fase 5 — Orquestador principal (/analyze/full)

### Descripción
Endpoint principal usado por el bot de WhatsApp y la extensión de Chrome. Recibe texto, URL e imagen simultáneamente y ejecuta todos los módulos correspondientes.

### Pseudocódigo

```
FUNCIÓN analyze_full(texto=null, url=null, imagen_base64=null):
    riesgos ← []

    SI texto no vacío:
        nlp_result  ← classify_text(texto)
        fact_result ← verify_claim(texto)
        riesgos.agregar(nlp_result.risk_level)

        SI fact_result.veredicto == "FALSO":
            fact_risk ← "alto" si confianza >= 0.7 else "medio"
            riesgos.agregar(fact_risk)

        try_collect_sample(texto, fact_result)  // Camino A

    SI url no vacía:
        url_result ← analyze_url(url)
        riesgos.agregar(url_result.risk_level)

    SI imagen_base64 no vacía:
        ocr_result ← extract_text_from_image(base64.decode(imagen_base64))
        SI ocr_result.has_text:
            img_nlp  ← classify_text(ocr_result.extracted_text)
            img_fact ← verify_claim(ocr_result.extracted_text)
            riesgos.agregar(img_nlp.risk_level)
            SI ocr_result.urls_found:
                img_url ← analyze_url(ocr_result.urls_found[0])
                riesgos.agregar(img_url.risk_level)

    overall_risk ← max(riesgos, orden: alto > medio > bajo > incierto)
    mensaje      ← format_response(resultados, canal)

    RETORNAR {overall_risk_level, ...resultados, formatted_message}
```

---

## Fase 6 — Retroalimentación automática (Camino A)

### Descripción
Cuando Google Fact Check devuelve un veredicto confiable, el texto se guarda automáticamente como muestra de entrenamiento. Las etiquetas provienen de organizaciones periodísticas internacionales (Newtral, ColombiaCheck, AFP Factual, BBC Verify, Snopes), no de usuarios — eliminando el riesgo de envenenamiento del dataset.

### Condiciones de calidad

| Condición | Valor |
|---|---|
| Fuente | `google_factcheck` (no fallback DuckDuckGo) |
| Veredicto | Solo `FALSO` o `VERDADERO` — nunca `INCIERTO` |
| Confianza | ≥ 0.80 |
| Longitud del texto | 20–2000 caracteres |

### Pseudocódigo

```
FUNCIÓN try_collect_sample(texto, fact_check_result):
    SI fact_check_result.source != "google_factcheck": RETORNAR false
    SI fact_check_result.veredicto NOT IN {"FALSO","VERDADERO"}: RETORNAR false
    SI fact_check_result.confianza < 0.80: RETORNAR false
    SI NOT (20 <= len(texto) <= 2000): RETORNAR false

    label ← "FAKE" si veredicto == "FALSO" else "REAL"
    hash  ← SHA256(texto)
    SI hash ya existe en training.db: RETORNAR false  // deduplicación

    INSERT INTO training_samples (hash, texto, label, veredicto,
                                  confianza, verificador, fuente, created_at)
    RETORNAR true
```

### Flujo de recolección y fine-tuning futuro

```
Texto analizado en producción
        ↓
verify_claim() → Google Fact Check API
        ↓
¿veredicto FALSO/VERDADERO, confianza ≥ 0.80, fuente = google_factcheck?
    ├── NO  → descartado silenciosamente
    └── SÍ  → INSERT en training.db (SQLite, sin datos del usuario)
                    ↓
    GET /training/stats  → monitorear acumulación
    POST /training/export → training_dataset.jsonl (JSONL)
                    ↓
    Fine-tuning en Google Colab (GPU T4 gratuita)
    modelo: analuciahm/tucuy-fake-news-spanish
    dataset: FakeDeS + muestras propias
                    ↓
    Evaluar accuracy — objetivo ≥ 90%
                    ↓
    Convertir a ONNX + cuantización int8 (~130MB)
                    ↓
    Desplegar en Render free (cabe en 512MB RAM)
```

### Endpoints de monitoreo

```
GET  /training/stats   → {total, fake, real, verificadores: [...]}
POST /training/export  → genera training_dataset.jsonl
```

---

## Fase 7 — Formateo de respuestas

### Descripción
Convierte resultados técnicos en mensajes legibles diferenciados por canal.

| Riesgo | WhatsApp | Extensión Chrome |
|---|---|---|
| Alto | 🔴 *¡CUIDADO!* + nombre verificador + enlace fuente | ⚠️ RIESGO ALTO: descripción corta |
| Medio | 🟡 *Ten precaución* + recomendación | ⚡ RIESGO MEDIO: descripción corta |
| Bajo | 🟢 *Este contenido parece seguro* | ✅ RIESGO BAJO |
| Incierto | 🔎 *No puedo verificar con certeza* | 🔎 NO SE PUEDE VERIFICAR |

WhatsApp usa markdown propio (`*negrita*`, `_cursiva_`). La extensión Chrome usa texto plano con emojis. El mismo resultado técnico produce mensajes distintos según el canal objetivo.

---

## Flujos de los canales de acceso

### Bot de WhatsApp (whatsapp-web.js + Puppeteer)

```
Mensaje entrante
    ├── hasMedia == true (imagen)
    │       ↓
    │   downloadMedia() → Buffer → POST /analyze/image (multipart)
    │       ↓
    │   OCR.space → texto → NLP → fact-check
    │
    ├── texto contiene URL (regex)
    │       ↓
    │   POST /analyze/full {text, url: primera URL encontrada}
    │       ↓
    │   NLP + Fact Check + Levenshtein simultáneo
    │
    └── solo texto
            ↓
        POST /analyze/text
            ↓
        NLP + Fact Check → risk_level unificado
```

### Extensión de Chrome (Manifest V3)

```
Al cargar cualquier página web
    ↓
content.js recolecta todos los <a href> HTTP/HTTPS
    ↓
background.js (service worker) recibe ANALYZE_URLS_BATCH
    ↓
analiza en grupos de 5 — timeout: 60s por grupo
    ↓
POST /analyze/url × N
    ↓
riesgo alto   → outline rojo + badge ⚠️ + tooltip al hover
riesgo medio  → outline naranja + badge 🟡 + tooltip al hover
riesgo bajo   → sin cambio visual
MutationObserver detecta cambios DOM (SPAs: Facebook, Twitter)

Clic derecho → "Verificar con Tucuy"
    ↓
POST /analyze/full — timeout: 120s
    ↓
overlay flotante animado con resultado
```

---

## Estado del despliegue en producción

| Componente | Estado | Notas |
|---|---|---|
| Backend FastAPI | ✅ Activo | `https://tucuy-backend.onrender.com` |
| Google Fact Check | ✅ Funcionando | Veredictos confiables elevan risk_level |
| Google Safe Browsing | ✅ Funcionando | Detecta MALWARE, PHISHING, SOCIAL_ENGINEERING |
| OCR.space | ✅ Funcionando | Extracción de texto en español |
| Levenshtein + Blacklist | ✅ Funcionando | Dominio peruano específico |
| OpenPhish | ✅ Funcionando | Feed público, sin API key |
| NLP (modelo completo) | ⚠️ Solo local | Excede 512MB RAM en Render free |
| NLP (fallback heurístico) | ✅ Activo en Render | Palabras clave, menor precisión |
| Extensión Chrome | ✅ Publicada | Chrome Web Store, apunta a Render |
| Bot WhatsApp | ✅ Funcional | Requiere escanear QR para activar |

---

## Estructura de archivos del proyecto

```
anti-desinformacion/
├── backend/
│   ├── main.py                       # API FastAPI — endpoints de análisis y entrenamiento
│   ├── modules/
│   │   ├── nlp.py                    # RoBERTa local + fallback heurístico
│   │   ├── levenshtein.py            # Detección typosquatting + blacklist
│   │   ├── ocr.py                    # OCR via OCR.space API
│   │   ├── fact_check.py             # Google Fact Check + DuckDuckGo
│   │   ├── url_checker.py            # 4 fuentes externas (GSB, URLhaus, OpenPhish, PhishTank)
│   │   ├── formatter.py              # Mensajes diferenciados por canal
│   │   └── training_collector.py     # Recolección automática de muestras (Camino A)
│   ├── data/
│   │   ├── dominios_legitimos.py     # Listas blanca (~45) y negra (~100) de dominios
│   │   ├── training.db               # SQLite — muestras acumuladas (generado en runtime)
│   │   └── training_dataset.jsonl    # Dataset exportado para fine-tuning
│   ├── scripts/
│   │   └── finetune_colab.py         # Script de fine-tuning para Google Colab
│   ├── Procfile                      # Comando arranque Render
│   ├── .python-version               # Python 3.11
│   └── requirements.txt
├── extension/
│   ├── background.js                 # Service worker (Manifest V3)
│   ├── content.js                    # Escaneo DOM + tooltips + overlay
│   ├── popup.html / popup.js         # UI 4 tabs: Texto, Enlace, Imagen, Todo
│   ├── manifest.json                 # Permisos y host_permissions
│   └── icons/                        # 16px, 48px, 128px, 512px
├── whatsapp-bot/
│   ├── index.js                      # Cliente whatsapp-web.js con manejo de todos los tipos
│   └── api_client.js                 # Axios client con manejo de errores unificado
├── docs/
│   └── privacy-policy.html           # Política de privacidad (GitHub Pages)
└── METODOLOGIA.md
```

---

## Variables de entorno del sistema

| Variable | Servicio | Gratuita | Estado en producción |
|---|---|---|---|
| `GOOGLE_FACTCHECK_KEY` | Google Fact Check Tools API | Sí | ✅ Configurada |
| `GOOGLE_SAFE_BROWSING_KEY` | Google Safe Browsing v4 | Sí | ✅ Configurada |
| `OCR_SPACE_KEY` | OCR.space API | Sí | ✅ Configurada |
| `HF_TOKEN` | Hugging Face (modelo local) | Sí | ✅ Configurada (sin efecto en Render free) |
| `URLHAUS_AUTH_KEY` | URLhaus / abuse.ch | Sí (registro) | Pendiente |
| `PHISHTANK_APP_KEY` | PhishTank | Sí | Opcional |

---

## Decisiones de diseño relevantes para el paper

1. **Fact-check como detector principal en producción**: dado que el modelo NLP completo no puede correr en el servidor gratuito, Google Fact Check actúa como detector primario. Cualquier afirmación verificada como FALSA por organizaciones periodísticas eleva directamente el risk_level, independientemente del NLP.

2. **Retroalimentación sin intervención humana (Camino A)**: las etiquetas de entrenamiento provienen de fact-checkers internacionales, no de usuarios. Esto elimina el riesgo de envenenamiento del dataset y no requiere moderadores.

3. **OCR como servicio externo**: migración de Tesseract local a OCR.space API para eliminar dependencias de binarios del sistema operativo, habilitando despliegue en Render.

4. **Degradación elegante en 3 niveles para NLP**: modelo local → fallback heurístico. El sistema nunca falla completamente aunque el modelo principal no esté disponible.

5. **Riesgo máximo como agregador**: cuando hay señales de múltiples módulos (NLP + URL + OCR + Fact-Check), se reporta el nivel más alto adoptando el principio de precaución.

6. **Contexto peruano explícito**: la blacklist y dominios legítimos fueron construidos específicamente para el ecosistema digital peruano: banca (BCP, BBVA, Interbank, Scotiabank, Banco de la Nación), gobierno (SUNAT, RENIEC, MINSA, MEF), pagos móviles (Yape, Plin), medios nacionales (El Comercio, RPP, Andina).

7. **Deduplicación SHA-256 del dataset**: evita que afirmaciones virales enviadas miles de veces contaminen el conjunto de entrenamiento con duplicados.

8. **Canal-aware formatting**: WhatsApp recibe markdown con lenguaje coloquial diseñado para adultos mayores; la extensión Chrome recibe texto plano conciso para uso en escritorio.
