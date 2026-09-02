# Sistema Anti-Desinformación — Lima Metropolitana

Sistema conversacional para detectar **fake news**, **enlaces fraudulentos (typosquatting)** y **contenido malicioso en imágenes**, accesible vía WhatsApp y extensión de navegador Chrome.

---

## Arquitectura del sistema

```
anti-desinformacion/
├── backend/               # API REST Python (FastAPI)
│   ├── main.py            # Aplicación principal + endpoints
│   ├── requirements.txt
│   ├── modules/
│   │   ├── nlp.py         # BETO HuggingFace (clasificación fake news)
│   │   ├── levenshtein.py # Detección typosquatting
│   │   ├── ocr.py         # pytesseract + Pillow
│   │   └── formatter.py   # Generador de mensajes amigables
│   ├── data/
│   │   └── dominios_legitimos.py  # ~50 dominios peruanos legítimos
│   └── tests/
│       ├── test_nlp.py
│       ├── test_levenshtein.py
│       ├── test_ocr.py
│       └── test_e2e.py    # 10 casos reales + métricas académicas
├── whatsapp-bot/          # Bot Node.js (whatsapp-web.js)
│   ├── index.js           # Bot principal
│   ├── api_client.js      # Cliente HTTP al backend
│   └── package.json
└── extension/             # Extensión Chrome (Manifest V3)
    ├── manifest.json
    ├── background.js      # Service worker + menú contextual
    ├── content.js         # Escaneo automático de URLs + overlay
    ├── popup.html         # Interfaz del popup
    ├── popup.js           # Lógica del popup
    └── icons/             # Iconos 16, 48, 128px
```

---

## Requisitos del sistema

### Backend (Python)
- Python 3.9 o superior
- `tesseract-ocr` instalado en el sistema (para OCR)
- Conexión a internet (primera ejecución: descarga el modelo BETO ~430MB)

### Bot WhatsApp (Node.js)
- Node.js 16 o superior
- npm 8 o superior

### Extensión Chrome
- Google Chrome 88 o superior (soporte Manifest V3)

---

## Instalación y ejecución

### 1. Backend FastAPI

```bash
cd anti-desinformacion/backend

# Instalar dependencias Python
pip3 install -r requirements.txt

# Instalar tesseract (macOS)
brew install tesseract tesseract-lang

# Instalar tesseract (Ubuntu/Debian)
# sudo apt-get install tesseract-ocr tesseract-ocr-spa

# Iniciar el servidor (queda corriendo en localhost:8000)
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

La documentación Swagger estará disponible en: http://localhost:8000/docs

### 2. Bot de WhatsApp

```bash
cd anti-desinformacion/whatsapp-bot

# Instalar dependencias Node.js
npm install

# Iniciar el bot
npm start
```

Al iniciar, se mostrará un **código QR en la terminal**. Escanéalo con WhatsApp:
1. Abre WhatsApp en tu teléfono
2. Ve a **Dispositivos vinculados** → **Vincular dispositivo**
3. Escanea el QR mostrado en la terminal

El bot quedará activo y responderá a mensajes entrantes.

### 3. Extensión de Chrome

1. Abre Chrome y ve a `chrome://extensions`
2. Activa el **Modo desarrollador** (switch en la esquina superior derecha)
3. Haz clic en **"Cargar extensión sin empaquetar"**
4. Selecciona la carpeta `extension/`
5. La extensión aparecerá en la barra de herramientas 🛡️

> **Importante:** El backend debe estar corriendo en `localhost:8000` para que la extensión funcione.

---

## Endpoints de la API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Estado del servidor |
| POST | `/analyze/text` | Analiza texto con BETO (fake news) |
| POST | `/analyze/url` | Detecta typosquatting con Levenshtein |
| POST | `/analyze/image` | OCR + NLP sobre imagen |
| POST | `/analyze/full` | Orquestador: texto + URL + imagen |

### Ejemplo de uso con curl

```bash
# Analizar texto
curl -X POST http://localhost:8000/analyze/text \
  -H "Content-Type: application/json" \
  -d '{"text": "El gobierno oculta la cura del COVID-19. Comparte antes de que borren esto."}'

# Analizar URL
curl -X POST http://localhost:8000/analyze/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://bcp-descuentos.com/oferta"}'

# Análisis completo
curl -X POST http://localhost:8000/analyze/full \
  -H "Content-Type: application/json" \
  -d '{"text": "Haz clic aquí para ganar", "url": "https://bcp-premios.com"}'
```

---

## Ejecutar pruebas

```bash
cd anti-desinformacion/backend

# Instalar dependencias de testing (si no están instaladas)
pip3 install pytest

# Ejecutar tests del módulo Levenshtein y OCR (rápidos, sin descargar modelo)
python3 -m pytest tests/test_levenshtein.py tests/test_ocr.py -v

# Ejecutar tests del módulo NLP (descarga el modelo la primera vez ~430MB)
python3 -m pytest tests/test_nlp.py -v

# Ejecutar evaluación completa e2e con métricas académicas
python3 tests/test_e2e.py

# Todos los tests
python3 -m pytest tests/ -v
```

---

## Módulos técnicos

### NLP — Clasificador BETO
- **Modelo:** `mrm8488/bert-base-spanish-wwm-cased-finetuned-fake-news` (HuggingFace)
- **Arquitectura:** BERT entrenado sobre corpus español (BETO) con fine-tuning para detección de fake news
- **Entrada:** Texto en español (máx. 512 tokens)
- **Salida:** Etiqueta `FAKE`/`REAL` + confianza (0–1) + nivel de riesgo

### Levenshtein — Detección de Typosquatting
- **Algoritmo:** Distancia de Levenshtein normalizada con estrategia de prefijo
- **Base de datos:** ~50 dominios peruanos legítimos (bancos, gobierno, medios)
- **Umbral:** Similitud ≥ 0.70 con dominio conocido → sospechoso
- **Estrategias de similitud:**
  1. Dominio completo (ej: `bbva-peru.net` vs `bbva.pe`)
  2. Nombre sin TLD (ej: `bbva-peru` vs `bbva`)
  3. Prefijo compartido (ej: `bcp-descuentos` empieza con `bcp` → alta sospecha)

### OCR — Extracción de texto en imágenes
- **Motor:** `pytesseract` con Tesseract OCR (Google)
- **Preprocesamiento:** Escala de grises → contraste aumentado → nitidez → escalado
- **Idioma:** Español (`-l spa`)
- **Salida:** Texto extraído + URLs detectadas dentro del texto

---

## Uso del Bot de WhatsApp

Envía cualquiera de estos contenidos al bot:

| Contenido | Respuesta del bot |
|-----------|-------------------|
| Texto de noticia | Análisis NLP: FAKE/REAL con explicación |
| Enlace (URL) | Verificación typosquatting + análisis de texto |
| Imagen/captura | OCR + análisis del texto extraído |
| "ayuda" | Instrucciones de uso |
| "hola" | Mensaje de bienvenida |

---

## Uso de la Extensión Chrome

| Acción | Descripción |
|--------|-------------|
| Clic en ícono 🛡️ | Abre popup para análisis manual de texto/URL |
| Visitar cualquier web | Escaneo automático de enlaces (marcado rojo/amarillo) |
| Pasar mouse sobre enlace marcado | Tooltip con explicación del riesgo |
| Seleccionar texto + clic derecho | Menú "Verificar con AntiDesinformación" |
| Resultado de menú contextual | Overlay en la página + notificación del sistema |

---

## Niveles de riesgo

| Nivel | Color | Significado |
|-------|-------|-------------|
| 🔴 Alto | Rojo | Desinformación confirmada o typosquatting evidente |
| 🟡 Medio | Amarillo | Señales sospechosas, verificar antes de compartir |
| 🟢 Bajo | Verde | Contenido aparentemente legítimo |

---

## Variables de entorno

| Variable | Valor por defecto | Descripción |
|----------|-------------------|-------------|
| `BACKEND_URL` | `http://localhost:8000` | URL del backend (para el bot de WhatsApp) |

---

## Limitaciones conocidas

- El modelo BETO requiere ~430MB de descarga en la primera ejecución
- OCR funciona mejor con imágenes de alta resolución y texto claro
- La extensión Chrome solo se comunica con `localhost:8000` (para demo local)
- whatsapp-web.js es una librería no oficial; puede requerir re-autenticación periódica

---

## Créditos

- Modelo NLP: [mrm8488/bert-base-spanish-wwm-cased-finetuned-fake-news](https://huggingface.co/mrm8488/bert-base-spanish-wwm-cased-finetuned-fake-news)
- OCR: [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- Bot WhatsApp: [whatsapp-web.js](https://github.com/pedroslopez/whatsapp-web.js)
