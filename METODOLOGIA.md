# Capítulo de Metodología — Sistema Tucuy
## Detección de Desinformación Digital para Lima Metropolitana

---

## Contexto general del sistema

**Nombre del sistema:** Tucuy (del quechua: "todo", "completo")  
**Objetivo:** Detectar desinformación digital, enlaces fraudulentos y noticias falsas dirigidas a ciudadanos de Lima Metropolitana, con énfasis en adultos mayores y personas con baja alfabetización digital.  
**Canales de acceso:** Extensión de Chrome, Bot de WhatsApp, API REST  
**Backend:** FastAPI (Python) desplegado en Render  
**URL producción:** `https://tucuy-backend.onrender.com`  
**Modelo NLP:** `Narrativaai/fake-news-detection-spanish` (RoBERTa fine-tuned para español) via Hugging Face Inference API  
**Fact-checking:** Google Fact Check Tools API + fallback DuckDuckGo  
**OCR:** OCR.space API (servicio externo, sin instalación de Tesseract)  
**Detección de URLs maliciosas:** Levenshtein + blacklist interna + 4 fuentes externas  

---

## Arquitectura del sistema (capas)

```
┌─────────────────────────────────────────────────────┐
│              CAPA DE PRESENTACIÓN                   │
│   Extensión Chrome   Bot WhatsApp   API directa     │
└──────────────────────┬──────────────────────────────┘
                       │ HTTPS REST
┌──────────────────────▼──────────────────────────────┐
│        API GATEWAY — FastAPI (Render)               │
│  /analyze/text  /analyze/url  /analyze/image        │
│  /analyze/full  /training/stats  /training/export   │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│           MÓDULOS DE ANÁLISIS (backend)             │
│  nlp.py │ levenshtein.py │ ocr.py │ fact_check.py  │
│  url_checker.py │ formatter.py │ training_collector │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              CAPA DE DATOS                          │
│  dominios_legitimos.py │ training.db (SQLite)       │
└─────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│           SERVICIOS EXTERNOS                        │
│  HF Inference API (RoBERTa) │ Google Fact Check     │
│  OCR.space │ Google Safe Browsing                   │
│  URLhaus │ OpenPhish │ PhishTank                    │
└─────────────────────────────────────────────────────┘
```

---

## Fase 1 — Análisis de texto (NLP)

### Descripción
Clasifica un texto en español como FAKE (desinformación) o REAL (legítimo) usando el modelo RoBERTa `Narrativaai/fake-news-detection-spanish`.

### Estrategia de inferencia (3 niveles en cascada)

En producción el modelo no se carga localmente para no exceder los límites de RAM del servidor. En su lugar se usa la **Hugging Face Inference API**, que corre el mismo modelo en los servidores de Hugging Face.

```
FUNCIÓN classify_text(texto):
    SI texto está vacío:
        RETORNAR {label: "REAL", confidence: 0.0, risk_level: "bajo"}

    // Estrategia 1: Hugging Face Inference API (producción)
    SI HF_TOKEN configurado:
        resultado ← POST https://api-inference.huggingface.co/models/
                         Narrativaai/fake-news-detection-spanish
                    body: {inputs: texto[:2000]}

        SI respuesta 503 (modelo dormido en HF):
            esperar 10s y reintentar

        SI respuesta OK:
            label     ← normalizar(resultado.label)
            confianza ← resultado.score
            RETORNAR {label, confidence, risk_level,
                      inference: "huggingface_api"}

    // Estrategia 2: pipeline local (desarrollo)
    pipeline ← cargar_modelo_roberta_local()
    SI pipeline disponible:
        resultado ← pipeline(texto[:2000])
        RETORNAR {label, confidence, risk_level, inference: "local"}

    // Estrategia 3: fallback heurístico
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

### Fallback heurístico (cuando HF API y pipeline local fallan)

```
FUNCIÓN fallback_heuristico(texto):
    KEYWORDS_FAKE = ["cura milagrosa", "el gobierno oculta",
                     "comparte antes de que borren", "urgente",
                     "ganaste", "premio", ...]  // 20 palabras clave

    coincidencias ← contar keywords en texto.lower()

    SI coincidencias >= 3: RETORNAR {label: "FAKE", confidence: 0.78}
    SI coincidencias >= 1: RETORNAR {label: "FAKE", confidence: 0.62}
    SINO:                  RETORNAR {label: "REAL", confidence: 0.85}
```

---

## Fase 2 — Verificación de hechos (Fact-Check)

### Descripción
Verifica si una afirmación ha sido investigada por organizaciones periodísticas internacionales (ColombiaCheck, AFP Factual, BBC Verify, Snopes, etc.) a través de la Google Fact Check Tools API.

### Pseudocódigo

```
FUNCIÓN verify_claim(texto):
    SI GOOGLE_FACTCHECK_KEY configurada:
        resultado ← google_factcheck_api(texto, idioma="es")

        SI hay resultados:
            rating      ← resultado.claimReview[0].textualRating
            verificador ← resultado.claimReview[0].publisher.name
            fuente      ← resultado.claimReview[0].url

            SI rating contiene ["falso", "false", "misleading", "engaño"]:
                RETORNAR {veredicto: "FALSO", confianza: 0.85,
                          verificador, fuente,
                          source: "google_factcheck"}

            SI rating contiene ["verdadero", "true", "correcto"]:
                RETORNAR {veredicto: "VERDADERO", confianza: 0.80,
                          source: "google_factcheck"}

    // Fallback: DuckDuckGo sin API key
    resultados ← duckduckgo_search(texto)
    puntuacion ← evaluar_resultados(resultados)
        // keywords FALSO vs keywords VERDADERO
        // peso doble para fuentes confiables (andina.pe, rpp.pe, bbc.com)

    RETORNAR {veredicto, confianza, source: "fact_check_ddg"}
```

### Información mostrada al usuario cuando hay fact-check confiable

```
• ❌ Verificación: FALSO (85% confianza) — verificado por ColombiaCheck
  "De nuevo, la tecnología 5G no es la causante del COVID-19"
  🔗 https://colombiacheck.com/...
```

---

## Fase 3 — Detección de URLs maliciosas

### Descripción
Detecta si una URL es un intento de typosquatting (imitación de sitios legítimos) o está en listas negras de phishing/malware. Usa tres niveles en cascada.

### Nivel 1 — Lista negra interna

```
FUNCIÓN check_blacklist(dominio):
    // ~100 dominios conocidos: phishing bancario peruano,
    // streaming pirata, casinos no regulados, malware

    // Estrategia 1: dominio exacto y subdominios
    PARA cada sufijo en partes del dominio:
        SI sufijo en DOMINIOS_BLACKLIST:
            RETORNAR {match: sufijo, reason: BLACKLIST_REASONS[sufijo]}

    // Estrategia 2: keywords (detecta variantes con TLD diferente)
    // Ej: cuevana3k.pro → contiene "cuevana"
    dominio_limpio ← dominio.replace("-", "").replace(".", "")
    PARA cada keyword en KEYWORD_RULES:
        SI keyword en dominio_limpio:
            RETORNAR {match: dominio, reason: KEYWORD_RULES[keyword]}

    RETORNAR null
```

### Nivel 2 — Fuentes externas

```
FUNCIÓN check_url_external(url):
    // 4 fuentes, degradación elegante si no hay API key
    resultados += google_safe_browsing(url)   // MALWARE, PHISHING
    resultados += urlhaus_abusedb(url)         // malware activo
    resultados += openphish_feed(url)          // caché local, TTL 1h
    resultados += phishtank(url)               // base comunitaria

    SI alguno detectó amenaza:
        RETORNAR {is_malicious: true, risk_level: "alto",
                  detections: [...fuentes que detectaron]}

    RETORNAR {is_malicious: false}
```

### Nivel 3 — Similitud Levenshtein

```
FUNCIÓN analyze_url(url):
    dominio ← extraer_dominio(url)

    // Paso 1: blacklist interna
    SI check_blacklist(dominio) → RETORNAR con source="blacklist"

    // Paso 2: fuentes externas
    SI check_url_external(url).is_malicious → RETORNAR con source="external"

    // Paso 3: similitud Levenshtein contra ~45 dominios legítimos peruanos
    PARA cada dominio_legitimo en DOMINIOS_LEGITIMOS:
        sim ← max(
            similitud_levenshtein(dominio, dominio_legitimo),
            similitud_levenshtein(sin_tld(dominio), sin_tld(dominio_legitimo)),
            bonus_prefijo(dominio, dominio_legitimo)
                // si "bcp" es prefijo de "bcp-descuentos" → score 0.65–0.90
        )

    SI mejor_similitud >= 0.85 → risk_level = "alto"
    SI mejor_similitud >= 0.70 → risk_level = "medio"

    RETORNAR {is_suspicious, closest_domain, similarity, risk_level,
              source: "levenshtein"}
```

---

## Fase 4 — OCR (análisis de imágenes)

### Descripción
Extrae el texto visible de una imagen usando **OCR.space API** (servicio externo). No requiere instalación de Tesseract en el servidor, lo que permite despliegue en entornos con recursos limitados.

### Cambio respecto al diseño original
El diseño inicial usaba Tesseract instalado localmente con Pillow para preprocesamiento. En producción se migró a OCR.space API para eliminar la dependencia de binarios del sistema operativo en Render.

### Pseudocódigo

```
FUNCIÓN extract_text_from_image(imagen_bytes):
    SI OCR_SPACE_KEY no configurada:
        RETORNAR error("OCR_SPACE_KEY no configurada")

    // Codificar imagen en base64
    image_b64  ← base64.encode(imagen_bytes)
    mime_type  ← detectar_mime(imagen_bytes)  // por magic bytes
    image_data ← "data:{mime_type};base64,{image_b64}"

    // Llamar a OCR.space API
    respuesta ← POST https://api.ocr.space/parse/image
        body: {
            base64image: image_data,
            language: "spa",       // español
            OCREngine: 2,          // motor más preciso
            scale: true,           // mejora imágenes pequeñas
            detectOrientation: true
        }
        headers: {apikey: OCR_SPACE_KEY}

    texto ← respuesta.ParsedResults[0].ParsedText
    has_text     ← len(texto sin espacios) >= 10
    urls_found   ← detectar_urls_regex(texto)
    confianza    ← min(1.0, len(texto) / 200)

    RETORNAR {extracted_text, has_text, confidence, urls_found, source: "ocr"}
```

---

## Fase 5 — Orquestador principal (/analyze/full)

### Descripción
Endpoint principal usado por el bot de WhatsApp y la extensión de Chrome. Recibe texto, URL e imagen simultáneamente y ejecuta todos los módulos correspondientes.

### Pseudocódigo

```
FUNCIÓN analyze_full(texto=null, url=null, imagen_base64=null):
    riesgos ← []
    resultados ← {}

    // Análisis de texto
    SI texto no vacío:
        nlp_result  ← classify_text(texto)       // HF API → RoBERTa
        fact_result ← verify_claim(texto)         // Google Fact Check
        riesgos.agregar(nlp_result.risk_level)
        SI fact_result.veredicto == "FALSO":
            riesgos.agregar("alto" si confianza >= 0.7 else "medio")

        // Recolección automática de entrenamiento (Camino A)
        try_collect_sample(texto, fact_result)

    // Análisis de URL
    SI url no vacía:
        url_result ← analyze_url(url)
        riesgos.agregar(url_result.risk_level)

    // Análisis de imagen
    SI imagen_base64 no vacía:
        ocr_result ← extract_text_from_image(base64.decode(imagen_base64))
        SI ocr_result.has_text:
            img_nlp  ← classify_text(ocr_result.extracted_text)
            img_fact ← verify_claim(ocr_result.extracted_text)
            riesgos.agregar(img_nlp.risk_level)
            SI ocr_result.urls_found:
                img_url ← analyze_url(ocr_result.urls_found[0])
                riesgos.agregar(img_url.risk_level)

    // Calcular riesgo global
    overall_risk ← max(riesgos, orden: alto > medio > bajo > incierto)
    mensaje      ← format_response(resultados, canal)

    RETORNAR {overall_risk_level, resultados..., formatted_message}
```

---

## Fase 6 — Retroalimentación automática (Camino A)

### Descripción
Cada análisis de texto que produce un veredicto confiable de Google Fact Check se guarda automáticamente como muestra de entrenamiento. La etiqueta proviene de organizaciones periodísticas internacionales, no de usuarios — eliminando el riesgo de datos maliciosos.

### Condiciones para guardar una muestra

| Condición | Valor requerido |
|---|---|
| Fuente del veredicto | `google_factcheck` (no fallback DuckDuckGo) |
| Veredicto | Solo `FALSO` o `VERDADERO` — nunca `INCIERTO` |
| Confianza | ≥ 0.80 |
| Longitud del texto | 20–2000 caracteres |

### Pseudocódigo

```
FUNCIÓN try_collect_sample(texto, fact_check_result):
    SI fact_check_result.source != "google_factcheck": RETORNAR false
    SI fact_check_result.veredicto NOT IN {"FALSO", "VERDADERO"}: RETORNAR false
    SI fact_check_result.confianza < 0.80: RETORNAR false
    SI len(texto) < 20 OR len(texto) > 2000: RETORNAR false

    label ← "FAKE" si veredicto == "FALSO" else "REAL"
    hash  ← SHA256(texto)
    SI hash ya existe en training.db: RETORNAR false  // deduplicación

    INSERT INTO training_samples (hash, texto, label, veredicto,
                                  confianza, verificador, fuente)
    RETORNAR true
```

### Flujo completo de recolección y fine-tuning

```
Usuario envía texto
        ↓
verify_claim(texto) → Google Fact Check API
        ↓
¿veredicto FALSO/VERDADERO con confianza >= 0.80?
    ├── NO  → descartado silenciosamente
    └── SÍ  → guardar en training.db (SQLite)
                    ↓
          (acumulación continua en producción)
                    ↓
    POST /training/export → training_dataset.jsonl
                    ↓
    fine-tuning en Google Colab (GPU gratuita)
    modelo base: Narrativaai/fake-news-detection-spanish
                    ↓
    publicar en Hugging Face Hub
    actualizar HF_TOKEN en producción
```

---

## Fase 7 — Formateo de respuestas

### Descripción
Convierte los resultados técnicos en mensajes legibles por canal.

| Riesgo | WhatsApp | Extensión Chrome |
|---|---|---|
| Alto | 🔴 *¡CUIDADO!* + verificador + enlace fuente | ⚠️ RIESGO ALTO: descripción corta |
| Medio | 🟡 *Ten precaución* + recomendación | ⚡ RIESGO MEDIO: descripción corta |
| Bajo | 🟢 *Este contenido parece seguro* | ✅ RIESGO BAJO |
| Incierto | 🔎 *No puedo verificar con certeza* | 🔎 NO SE PUEDE VERIFICAR |

---

## Flujos de los canales de acceso

### Bot de WhatsApp

```
Mensaje entrante
    ├── hasMedia == true
    │       ↓
    │   downloadMedia() → Buffer
    │       ↓
    │   POST /analyze/image (multipart)
    │       ↓
    │   OCR.space API → texto → NLP (HF API) → fact-check
    │
    ├── texto contiene URL
    │       ↓
    │   POST /analyze/full {text, url}
    │       ↓
    │   NLP (HF API) + Fact Check + Levenshtein
    │
    └── solo texto
            ↓
        POST /analyze/text
            ↓
        NLP (HF API) + Fact Check
```

### Extensión de Chrome

```
Al cargar página
    ↓
content.js recolecta todos los <a href>
    ↓
ANALYZE_URLS_BATCH → background.js
    ↓
analiza en grupos de 5 — timeout: 60s
    ↓
POST /analyze/url × N  →  Levenshtein + blacklist + fuentes externas
    ↓
riesgo alto   → outline rojo + badge ⚠️ + tooltip
riesgo medio  → outline naranja + badge 🟡 + tooltip
riesgo bajo   → sin cambio visual

Clic derecho en texto o enlace
    ↓
POST /analyze/full — timeout: 120s (carga modelo HF si está dormido)
    ↓
overlay flotante con resultado
```

---

## Estructura de archivos del proyecto

```
anti-desinformacion/
├── backend/
│   ├── main.py                      # API FastAPI — 5 endpoints análisis
│   │                                # + 2 endpoints entrenamiento
│   ├── modules/
│   │   ├── nlp.py                   # RoBERTa via HF Inference API
│   │   ├── levenshtein.py           # Detección typosquatting
│   │   ├── ocr.py                   # OCR via OCR.space API
│   │   ├── fact_check.py            # Google Fact Check + DuckDuckGo
│   │   ├── url_checker.py           # 4 fuentes externas
│   │   ├── formatter.py             # Mensajes por canal
│   │   └── training_collector.py    # Recolección automática muestras
│   ├── data/
│   │   ├── dominios_legitimos.py    # Listas blanca y negra de dominios
│   │   ├── training.db              # SQLite (generado en runtime)
│   │   └── training_dataset.jsonl   # Dataset exportado para fine-tuning
│   ├── Procfile                     # Comando de arranque para Render
│   ├── .python-version              # Fuerza Python 3.11
│   ├── requirements.txt
│   └── RETROALIMENTACION.md
├── extension/
│   ├── background.js                # Service worker — puente con backend
│   ├── content.js                   # Escaneo de página + tooltips
│   ├── popup.html / popup.js        # UI con 4 tabs
│   ├── manifest.json                # Manifest V3
│   └── icons/                       # 16, 48, 128, 512px
├── whatsapp-bot/
│   ├── index.js                     # Cliente whatsapp-web.js
│   └── api_client.js                # Cliente axios al backend
└── METODOLOGIA.md
```

---

## Variables de entorno requeridas

| Variable | Servicio | Gratuita | Prioridad |
|---|---|---|---|
| `GOOGLE_FACTCHECK_KEY` | Google Fact Check Tools | Sí | Core |
| `HF_TOKEN` | Hugging Face Inference API | Sí | Core |
| `OCR_SPACE_KEY` | OCR.space | Sí | Core |
| `GOOGLE_SAFE_BROWSING_KEY` | Google Safe Browsing v4 | Sí | Recomendada |
| `URLHAUS_AUTH_KEY` | URLhaus / abuse.ch | Sí (registro) | Recomendada |
| `PHISHTANK_APP_KEY` | PhishTank | Sí | Opcional |

Sin `HF_TOKEN` el NLP usa el fallback heurístico de palabras clave. Sin las demás keys el sistema sigue operativo con blacklist local, Levenshtein y OpenPhish.

---

## Decisiones de diseño relevantes para el paper

1. **Inferencia remota del modelo NLP**: en producción el modelo RoBERTa se invoca via Hugging Face Inference API en lugar de cargarse localmente, eliminando el requisito de ~1.5GB de RAM en el servidor. El modelo usado es idéntico, solo cambia dónde corre.

2. **OCR como servicio externo**: se migró de Tesseract local a OCR.space API para evitar la instalación de binarios del sistema operativo en entornos cloud con recursos limitados.

3. **Degradación elegante en 3 niveles para NLP**: HF Inference API → pipeline local → heurística de palabras clave. El sistema nunca falla completamente.

4. **Retroalimentación automática sin intervención humana**: las etiquetas de entrenamiento provienen de organizaciones de fact-checking internacionales (Google Fact Check), no de usuarios, eliminando el riesgo de envenenamiento del dataset.

5. **Deduplicación por hash SHA-256**: evita que afirmaciones virales (enviadas miles de veces) contaminen el dataset con duplicados.

6. **Canal-aware formatting**: el mismo resultado técnico produce mensajes distintos según el canal. WhatsApp recibe markdown con lenguaje coloquial para adultos mayores; la extensión Chrome recibe texto plano conciso.

7. **Riesgo máximo como agregador**: cuando hay múltiples señales (NLP + URL + OCR), el sistema reporta el nivel más alto, adoptando el principio de precaución.

8. **Contexto peruano explícito**: la blacklist y lista de dominios legítimos están construidas específicamente para el ecosistema digital peruano (BCP, BBVA, SUNAT, RENIEC, Yape, medios nacionales).
