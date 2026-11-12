# Manual Técnico — Sistema Tucuy
## Aplicación Conversacional Híbrida para la Mitigación de la Desinformación y el Phishing
**Versión:** 1.0.0 | **Fecha:** Octubre 2026  
**Equipo:** Hernandez Mendoza, A. · Montoya Bravo, F. · Sanchez Chigne, A.

---

## 1. Descripción General del Sistema

Tucuy es un sistema híbrido multicanal para detectar desinformación digital, noticias falsas y enlaces fraudulentos dirigido a ciudadanos de Lima Metropolitana. Opera a través de tres canales: extensión de Chrome, bot de WhatsApp y API REST.

**URL de producción:** `https://tucuy-backend.onrender.com`  
**Repositorio:** `https://github.com/MeAnd17/anti-desinformacion`

---

## 2. Arquitectura del Sistema

```
┌─────────────────────────────────────────────────┐
│           CAPA DE PRESENTACIÓN                  │
│  Extensión Chrome (MV3)  Bot WhatsApp (Baileys) │
└──────────────────────┬──────────────────────────┘
                       │ HTTPS REST
┌──────────────────────▼──────────────────────────┐
│         API GATEWAY — FastAPI (Render)           │
│  /analyze/text  /analyze/url  /analyze/image     │
│  /analyze/full  /training/stats                  │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│            MÓDULOS DE ANÁLISIS                  │
│  nlp.py · levenshtein.py · ocr.py               │
│  fact_check.py · url_checker.py · formatter.py  │
│  training_collector.py                          │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│            SERVICIOS EXTERNOS                   │
│  Google Fact Check · Google Safe Browsing        │
│  OCR.space · OpenPhish · URLhaus · PhishTank     │
│  Hugging Face (modelo ONNX)                      │
└─────────────────────────────────────────────────┘
```

---

## 3. Requisitos de Infraestructura

### Backend
| Componente | Versión |
|---|---|
| Python | 3.11.x |
| FastAPI | 0.111.0 |
| Uvicorn | 0.29.0 |
| optimum[onnxruntime] | 1.19.1 |
| transformers | 4.40.2 |
| RAM mínima | 512 MB |

### Bot de WhatsApp
| Componente | Versión |
|---|---|
| Node.js | ≥ 18 LTS |
| @whiskeysockets/baileys | 6.7.16 |
| axios | 1.7.2 |

### Extensión Chrome
| Requisito | Valor |
|---|---|
| Manifest Version | V3 |
| Chrome mínimo | 88+ |
| Permisos | activeTab, contextMenus, storage, notifications |

---

## 4. Variables de Entorno

Crear archivo `backend/.env` con las siguientes claves:

```env
# Google Fact Check Tools API (gratuita)
# https://developers.google.com/fact-check/tools/api
GOOGLE_FACTCHECK_KEY=

# Google Safe Browsing API v4 (gratuita)
# https://developers.google.com/safe-browsing
GOOGLE_SAFE_BROWSING_KEY=

# OCR.space API (gratuita)
# https://ocr.space/ocrapi
OCR_SPACE_KEY=

# URLhaus — abuse.ch (gratuita, requiere registro)
# https://urlhaus-api.abuse.ch
URLHAUS_AUTH_KEY=

# PhishTank (opcional)
# https://www.phishtank.com/api_info.php
PHISHTANK_APP_KEY=
```

En **Render**, estas variables se configuran en: Dashboard → Servicio → Environment.

---

## 5. Despliegue en Producción (Render)

### 5.1 Configuración inicial
1. Crear cuenta en [render.com](https://render.com)
2. New Project → **Web Service** → conectar repositorio GitHub
3. Configurar:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Agregar variables de entorno en la sección **Environment**
5. Clic en **Deploy**

### 5.2 Redeploy automático
Render detecta cada push a la rama `main` y ejecuta el redeploy automáticamente. No se requiere intervención manual.

### 5.3 Verificar despliegue
```
GET https://tucuy-backend.onrender.com/health
→ {"status": "ok", "version": "1.0.0"}
```

---

## 6. Instalación en Entorno Local

```bash
# Clonar repositorio
git clone https://github.com/MeAnd17/anti-desinformacion.git
cd anti-desinformacion/backend

# Crear entorno virtual
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Crear .env con las claves API
# (ver sección 4)

# Ejecutar servidor
uvicorn main:app --reload --port 8000
```

---

## 7. Módulos del Backend

### 7.1 nlp.py — Clasificación de fake news
- **Modelo:** `analuciahm/tucuy-fake-news-spanish-onnx` (RoBERTa cuantizado, 119MB)
- **Runtime:** onnxruntime (sin torch en producción)
- **Carga:** lazy loading al primer request
- **Fallback:** clasificador heurístico por palabras clave

### 7.2 levenshtein.py — Detección de typosquatting
- **Nivel 1:** blacklist interna (~100 dominios peruanos peligrosos)
- **Nivel 2:** fuentes externas (Safe Browsing, URLhaus, OpenPhish, PhishTank)
- **Nivel 3:** similitud Levenshtein contra ~45 dominios legítimos peruanos
- **Umbral:** similitud ≥ 0.70 → sospechoso, ≥ 0.85 → alto riesgo

### 7.3 ocr.py — Extracción de texto en imágenes
- **Servicio:** OCR.space API
- **Idioma:** español (motor LSTM)
- **Input:** JPEG, PNG, WebP, GIF

### 7.4 fact_check.py — Verificación de hechos
- **Primario:** Google Fact Check Tools API
- **Fallback:** DuckDuckGo Instant Answer API
- **Efecto:** veredicto FALSO con confianza ≥ 0.70 eleva risk_level a "alto"

### 7.5 training_collector.py — Retroalimentación automática
- Guarda muestras de entrenamiento cuando Google Fact Check devuelve veredicto confiable
- Base de datos: `data/training.db` (SQLite)
- Deduplicación por SHA-256

---

## 8. Endpoints de la API

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/health` | Estado del servidor |
| POST | `/analyze/text` | Análisis de texto/noticia |
| POST | `/analyze/url` | Análisis de URL |
| POST | `/analyze/image` | Análisis de imagen (multipart) |
| POST | `/analyze/full` | Análisis combinado |
| GET | `/training/stats` | Estadísticas del dataset |
| POST | `/training/export` | Exportar dataset JSONL |

Documentación interactiva (Swagger): `https://tucuy-backend.onrender.com/docs`

---

## 9. Bot de WhatsApp

### 9.1 Instalación
```bash
cd whatsapp-bot
npm install
```

### 9.2 Configurar URL del backend
El bot apunta a `https://tucuy-backend.onrender.com` por defecto. Para usar backend local:
```bash
BACKEND_URL=http://localhost:8000 node index.js
```

### 9.3 Ejecución
```bash
node index.js
```
Escanear el código QR con WhatsApp → Dispositivos vinculados → Vincular dispositivo.

### 9.4 Tipos de mensaje soportados
| Tipo | Endpoint llamado |
|---|---|
| Solo texto | POST /analyze/text |
| Texto + URL | POST /analyze/full |
| Imagen | POST /analyze/image |

---

## 10. Extensión Chrome

### 10.1 Instalación en modo desarrollador
1. Abrir `chrome://extensions/`
2. Activar **Modo desarrollador**
3. Clic en **Cargar descomprimida**
4. Seleccionar la carpeta `extension/`

### 10.2 Actualización del backend URL
Si el backend cambia de URL, editar `extension/background.js`:
```javascript
const BACKEND_URL = "https://nueva-url.onrender.com";
```
Luego recargar la extensión en `chrome://extensions/`.

---

## 11. Actualización del Modelo NLP

1. Realizar fine-tuning en Google Colab usando `backend/scripts/finetune_colab.py`
2. El script exporta automáticamente a ONNX cuantizado y sube a `analuciahm/tucuy-fake-news-spanish-onnx`
3. El backend cargará el nuevo modelo en el próximo arranque (lazy loading)
4. Verificar con: `POST /analyze/text` → campo `inference` debe decir `"onnx"`

---

## 12. Solución de Problemas Frecuentes

| Problema | Causa | Solución |
|---|---|---|
| Servidor responde 502 | RAM excedida en Render | Verificar que torch/transformers no estén en requirements.txt |
| NLP usa fallback heurístico | Modelo ONNX no cargó | Verificar logs en Render — puede ser error de dependencias |
| OCR devuelve error 400 | OCR_SPACE_KEY no configurada | Agregar key en Render → Environment |
| Bot no descarga imágenes | Sesión de WhatsApp expirada | Borrar `.baileys_auth/` y re-escanear QR |
| Safe Browsing no detecta | GOOGLE_SAFE_BROWSING_KEY faltante | Configurar key en Render → Environment |
