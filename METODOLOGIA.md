# Capítulo de Metodología — Sistema Tucuy
## Detección de Desinformación Digital para Lima Metropolitana

---

## Contexto general del sistema

**Nombre del sistema:** Tucuy (del quechua: "todo", "completo")  
**Objetivo:** Detectar desinformación digital, enlaces fraudulentos y noticias falsas dirigidas a ciudadanos de Lima Metropolitana, con énfasis en adultos mayores y personas con baja alfabetización digital.  
**Canales de acceso:** Extensión de Chrome, Bot de WhatsApp, API REST  
**Backend:** FastAPI (Python)  
**Modelo NLP:** `Narrativaai/fake-news-detection-spanish` (RoBERTa fine-tuned para español)  
**Fact-checking:** Google Fact Check Tools API + fallback DuckDuckGo  
**OCR:** Tesseract con preprocesamiento Pillow  
**Detección de URLs maliciosas:** Levenshtein + blacklist interna + 4 fuentes externas  

---

## Arquitectura del sistema (capas)

```
┌─────────────────────────────────────────────────────┐
│              CAPA DE PRESENTACIÓN                   │
│   Extensión Chrome   Bot WhatsApp   API directa     │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP REST
┌──────────────────────▼──────────────────────────────┐
│              API GATEWAY — FastAPI                  │
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
│  Google Fact Check │ Google Safe Browsing           │
│  URLhaus │ OpenPhish │ PhishTank                    │
└─────────────────────────────────────────────────────┘
```

---

## Fase 1 — Análisis de texto (NLP)

### Descripción
Clasifica un texto en español como FAKE (desinformación) o REAL (legítimo) usando un modelo de lenguaje RoBERTa fine-tuned para fake news en español.

### Modelo utilizado
- `Narrativaai/fake-news-detection-spanish` (Hugging Face)
- Carga diferida (lazy loading): se instancia solo en la primera llamada
- Truncado automático a 512 tokens

### Pseudocódigo

```
FUNCIÓN classify_text(texto):
    SI texto está vacío:
        RETORNAR {label: "REAL", confidence: 0.0, risk_level: "bajo"}

    pipeline ← cargar_modelo_roberta()  // lazy loading

    SI pipeline no disponible:
        RETORNAR fallback_heuristico(texto)

    resultado ← pipeline(texto[:2000])
    etiqueta  ← normalizar_etiqueta(resultado.label)
        // LABEL_1, 1, FAKE, FALSO → "FAKE"
        // resto → "REAL"

    confianza ← resultado.score

    SI etiqueta == "FAKE":
        SI confianza > 0.85 → risk_level = "alto"
        SI confianza >= 0.60 → risk_level = "medio"
        SI confianza < 0.60  → risk_level = "bajo"
    SINO:
        risk_level = "bajo"

    RETORNAR {label, confidence, risk_level, source: "nlp"}
```

### Fallback heurístico (cuando el modelo no está disponible)

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
    SI GOOGLE_API_KEY configurada:
        resultado ← google_factcheck_api(texto, idioma="es")

        SI hay resultados:
            rating ← resultado.claimReview[0].textualRating

            SI rating contiene ["falso", "false", "misleading", "engaño"]:
                RETORNAR {veredicto: "FALSO", confianza: 0.85,
                          fuente: url, verificador: nombre_medio,
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
    resultados ← []

    // 4 fuentes en paralelo, degradación elegante si no hay API key
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
        // quitar https://, www., puerto

    // Paso 1: blacklist interna
    SI check_blacklist(dominio) → RETORNAR con source="blacklist"

    // Paso 2: fuentes externas
    SI check_url_external(url).is_malicious → RETORNAR con source="external"

    // Paso 3: similitud Levenshtein contra ~45 dominios legítimos peruanos
    // (BCP, BBVA, SUNAT, RENIEC, El Comercio, RPP, Yape, etc.)
    mejor_similitud ← 0.0
    mejor_dominio   ← null

    PARA cada dominio_legitimo en DOMINIOS_LEGITIMOS:
        sim ← max(
            similitud_levenshtein(dominio, dominio_legitimo),
            similitud_levenshtein(sin_tld(dominio), sin_tld(dominio_legitimo)),
            bonus_prefijo(dominio, dominio_legitimo)
                // si "bcp" es prefijo de "bcp-descuentos" → score 0.65–0.90
        )
        SI sim > mejor_similitud:
            mejor_similitud ← sim
            mejor_dominio   ← dominio_legitimo

    SI mejor_similitud >= 0.70 Y dominio != mejor_dominio:
        is_suspicious ← true
        SI mejor_similitud >= 0.85 → risk_level = "alto"
        SI mejor_similitud >= 0.70 → risk_level = "medio"

    RETORNAR {is_suspicious, closest_domain, similarity, risk_level,
              source: "levenshtein"}
```

---

## Fase 4 — OCR (análisis de imágenes)

### Descripción
Extrae el texto visible de una imagen para analizarlo con NLP y detectar URLs en él.

### Pseudocódigo

```
FUNCIÓN extract_text_from_image(imagen_bytes):
    imagen ← Image.open(imagen_bytes)

    // Preprocesamiento para mejorar calidad OCR
    imagen ← convertir_escala_grises(imagen)
    imagen ← aumentar_contraste(imagen, factor=2.0)
    imagen ← aumentar_nitidez(imagen, factor=2.0)
    SI ancho(imagen) < 800px:
        imagen ← escalar(imagen, ancho=800px)  // LANCZOS

    // Extracción de texto
    config_tesseract ← "--oem 3 --psm 3 -l spa"
        // oem 3 = motor LSTM
        // psm 3 = segmentación automática de página
        // spa   = idioma español
    texto ← tesseract.image_to_string(imagen, config)

    // Post-procesamiento
    texto ← limpiar_espacios_multiples(texto)
    has_text ← len(texto sin espacios) >= 10
    urls_encontradas ← detectar_urls_regex(texto)
    confianza ← min(1.0, len(texto) / 200)  // heurística por longitud

    RETORNAR {extracted_text, has_text, confidence, urls_found}
```

---

## Fase 5 — Orquestador principal (/analyze/full)

### Descripción
Endpoint que recibe texto, URL e imagen de forma simultánea y ejecuta todos los módulos que correspondan. Es el endpoint principal usado por el bot de WhatsApp y la extensión de Chrome.

### Pseudocódigo

```
FUNCIÓN analyze_full(texto=null, url=null, imagen_base64=null):
    riesgos ← []
    resultados ← {}

    // Análisis de texto
    SI texto no vacío:
        nlp_result  ← classify_text(texto)
        fact_result ← verify_claim(texto)
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
        imagen_bytes ← base64.decode(imagen_base64)
        ocr_result   ← extract_text_from_image(imagen_bytes)
        SI ocr_result.has_text:
            img_nlp  ← classify_text(ocr_result.extracted_text)
            img_fact ← verify_claim(ocr_result.extracted_text)
            riesgos.agregar(img_nlp.risk_level)
            SI ocr_result.urls_found:
                img_url ← analyze_url(ocr_result.urls_found[0])
                riesgos.agregar(img_url.risk_level)

    // Calcular riesgo global (máximo de todos los riesgos)
    overall_risk ← max(riesgos, orden: alto > medio > bajo > incierto)

    // Generar mensaje amigable
    mensaje ← format_response(resultados, canal)

    RETORNAR {overall_risk_level, resultados..., formatted_message}
```

---

## Fase 6 — Retroalimentación automática (Camino A)

### Descripción
Cada análisis de texto que produce un veredicto confiable de Google Fact Check se guarda automáticamente como muestra de entrenamiento. La etiqueta proviene de organizaciones periodísticas, no de usuarios.

### Condiciones para guardar una muestra

| Condición | Valor requerido |
|---|---|
| Fuente del veredicto | `google_factcheck` (no fallback DuckDuckGo) |
| Veredicto | Solo `FALSO` o `VERDADERO` |
| Confianza | ≥ 0.80 |
| Longitud del texto | 20–2000 caracteres |

### Pseudocódigo

```
FUNCIÓN try_collect_sample(texto, fact_check_result):
    // Validaciones de calidad
    SI fact_check_result.source != "google_factcheck": RETORNAR false
    SI fact_check_result.veredicto NOT IN {"FALSO", "VERDADERO"}: RETORNAR false
    SI fact_check_result.confianza < 0.80: RETORNAR false
    SI len(texto) < 20 OR len(texto) > 2000: RETORNAR false

    // Mapear veredicto a etiqueta del modelo
    label ← "FAKE" si veredicto == "FALSO" else "REAL"

    // Deduplicación
    hash ← SHA256(texto)
    SI hash ya existe en training.db: RETORNAR false

    // Persistir en SQLite
    INSERT INTO training_samples (hash, texto, label, veredicto,
                                  confianza, verificador, fuente)
    RETORNAR true


FUNCIÓN export_dataset(output_path):
    filas ← SELECT * FROM training_samples ORDER BY created_at
    PARA cada fila:
        ESCRIBIR en JSONL: {text, label, veredicto, confianza, verificador}
    RETORNAR archivo .jsonl listo para fine-tuning
```

### Flujo completo de recolección

```
Usuario envía texto
        ↓
verify_claim(texto)
        ↓
¿veredicto FALSO/VERDADERO con confianza >= 0.80?
    ├── NO  → descartado (sin efecto en el sistema)
    └── SÍ  → guardar en training.db
                    ↓
              (acumulación continua)
                    ↓
POST /training/export
                    ↓
        training_dataset.jsonl
                    ↓
    fine-tuning del modelo RoBERTa
```

---

## Fase 7 — Formateo de respuestas

### Descripción
Convierte los resultados técnicos en mensajes legibles, diferenciando por canal (WhatsApp usa markdown propio, la extensión de Chrome usa texto plano con emojis).

### Niveles de riesgo y mensajes

| Riesgo | WhatsApp | Extensión Chrome |
|---|---|---|
| Alto | 🔴 *¡CUIDADO!* con detalles del verificador y enlace | ⚠️ RIESGO ALTO: descripción corta |
| Medio | 🟡 *Ten precaución* con recomendación de verificar | ⚡ RIESGO MEDIO: descripción corta |
| Bajo | 🟢 *Este contenido parece seguro* | ✅ RIESGO BAJO |
| Incierto | 🔎 *No puedo verificar con certeza* | 🔎 NO SE PUEDE VERIFICAR |

### Información mostrada cuando hay fact-check confiable

```
• ❌ Verificación: FALSO (85% confianza) — verificado por ColombiaCheck
  "De nuevo, la tecnología 5G no es la causante del COVID-19"
  🔗 https://colombiacheck.com/...
```

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
    │   OCR → NLP → (URL si hay en el texto)
    │
    ├── texto contiene URL
    │       ↓
    │   POST /analyze/full {text, url}
    │       ↓
    │   NLP + Fact Check + Levenshtein simultáneo
    │
    └── solo texto
            ↓
        POST /analyze/text
            ↓
        NLP + Fact Check
```

### Extensión de Chrome

```
Al cargar página
    ↓
content.js recolecta todos los <a href>
    ↓
ANALYZE_URLS_BATCH → background.js
    ↓
analiza en grupos de 5 (no saturar backend)
    ↓
POST /analyze/url × N
    ↓
riesgo alto   → outline rojo + badge ⚠️ + tooltip
riesgo medio  → outline naranja + badge 🟡 + tooltip
riesgo bajo   → sin cambio visual

Clic derecho en texto o enlace
    ↓
POST /analyze/full
    ↓
overlay flotante con resultado
```

---

## Estructura de archivos del backend

```
backend/
├── main.py                          # API FastAPI, 5 endpoints de análisis
│                                    # + 2 endpoints de entrenamiento
├── modules/
│   ├── nlp.py                       # Clasificación fake news (RoBERTa)
│   ├── levenshtein.py               # Detección typosquatting
│   ├── ocr.py                       # Extracción texto de imágenes
│   ├── fact_check.py                # Verificación Google FC + DDG
│   ├── url_checker.py               # 4 fuentes externas (GSB, URLhaus, etc.)
│   ├── formatter.py                 # Generación de mensajes por canal
│   └── training_collector.py        # Recolección automática de muestras
├── data/
│   ├── dominios_legitimos.py        # Listas blanca y negra de dominios
│   ├── training.db                  # SQLite con muestras acumuladas
│   └── training_dataset.jsonl       # Dataset exportado para fine-tuning
├── tests/
│   ├── test_nlp.py
│   ├── test_levenshtein.py
│   ├── test_ocr.py
│   └── test_e2e.py
├── .env                             # API keys (no subir a GitHub)
├── requirements.txt
└── RETROALIMENTACION.md             # Documentación del Camino A
```

---

## Variables de entorno requeridas

| Variable | API | Gratuita | Requerida |
|---|---|---|---|
| `GOOGLE_FACTCHECK_KEY` | Google Fact Check Tools | Sí | Sí (core) |
| `GOOGLE_SAFE_BROWSING_KEY` | Google Safe Browsing v4 | Sí | Recomendada |
| `URLHAUS_AUTH_KEY` | URLhaus / abuse.ch | Sí (registro) | Recomendada |
| `PHISHTANK_APP_KEY` | PhishTank | Sí | Opcional |

Sin ninguna key el sistema funciona en modo degradado: NLP, blacklist local, Levenshtein y OpenPhish (sin key) siguen activos.

---

## Decisiones de diseño relevantes para el paper

1. **Degradación elegante**: cada módulo externo puede fallar sin detener el sistema. Si Google Safe Browsing no tiene key, se omite y los demás continúan.

2. **Lazy loading del modelo NLP**: el modelo RoBERTa se carga solo cuando llega la primera petición, reduciendo el tiempo de arranque del servidor.

3. **Deduplicación por hash**: las muestras de entrenamiento se identifican por SHA-256 del texto limpio, evitando que la misma afirmación viral contamine el dataset con duplicados.

4. **Canal-aware formatting**: el mismo resultado técnico produce mensajes distintos según el canal. WhatsApp recibe markdown con emojis y lenguaje coloquial; la extensión recibe texto plano más conciso.

5. **Riesgo máximo como agregador**: cuando hay múltiples señales de riesgo (NLP + URL + OCR), el sistema reporta el nivel más alto, adoptando el principio de precaución.

6. **Contexto peruano explícito**: la lista de dominios legítimos y la blacklist están construidas específicamente para el ecosistema digital peruano (BCP, BBVA, SUNAT, RENIEC, Yape, medios nacionales).
