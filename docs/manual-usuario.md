# Manual de Usuario — Sistema Tucuy
## Guía paso a paso para verificar noticias, enlaces e imágenes
**Versión:** 1.0.0 | **Fecha:** Octubre 2026

---

## ¿Qué es Tucuy?

Tucuy es tu asistente digital para protegerte de noticias falsas, enlaces peligrosos y estafas en internet. Su nombre viene del quechua y significa "todo" — porque analiza todo tipo de contenido digital.

Puedes usar Tucuy de **dos formas**:
- 📱 **Por WhatsApp** — envía un mensaje al bot desde tu celular
- 🌐 **Por la extensión de Chrome** — te protege automáticamente mientras navegas

---

## PARTE 1: Bot de WhatsApp

### ¿Cómo activarlo?

El bot debe estar corriendo en la computadora del equipo. Una vez activo, busca el número de WhatsApp de Tucuy en tus contactos y escríbele.

Al primer mensaje recibirás un mensaje de bienvenida con el menú de opciones.

---

### Verificar un texto o noticia

**¿Cuándo usarlo?** Cuando recibes una noticia, cadena o mensaje que te parece sospechoso.

**Pasos:**
1. Copia el texto que quieres verificar
2. Pégalo en el chat de Tucuy
3. Espera la respuesta (puede tardar unos segundos)

**Ejemplo:**
```
Tú: "El gobierno peruano oculta la cura del COVID-19, 
      comparte antes de que lo borren"

Tucuy: 🔴 ¡CUIDADO! Este mensaje parece ser una noticia 
        falsa (confianza: 85%).
        ❌ Verificación: FALSO — verificado por ColombiaCheck
        👉 No lo compartas.
```

---

### Verificar un enlace (URL)

**¿Cuándo usarlo?** Cuando recibes un link que dice ser del BCP, SUNAT, Yape u otra entidad oficial.

**Pasos:**
1. Copia el enlace completo (por ejemplo: `https://bcp-descuentos.com`)
2. Pégalo en el chat de Tucuy
3. Tucuy detectará si es una imitación del sitio real

**Ejemplo:**
```
Tú: https://bcp-descuentos.com/oferta

Tucuy: 🟡 Este enlace es sospechoso.
        Se parece mucho al sitio oficial de bcp.com.pe
        pero tiene diferencias en la dirección web.
        ⚠️ Enlace recibido: bcp-descuentos.com
        ✅ Sitio real: bcp.com.pe
        👉 No ingreses tus datos.
```

---

### Verificar una imagen o captura de pantalla

**¿Cuándo usarlo?** Cuando alguien te manda una foto con una noticia, un afiche o un mensaje escrito.

**Pasos:**
1. Abre el chat de Tucuy en WhatsApp
2. Adjunta la imagen directamente (como si fuera una foto)
3. Envíala
4. Tucuy leerá el texto de la imagen y lo analizará

**Ejemplo:**
```
[Envías una captura de pantalla con texto sobre vacunas]

Tucuy: 🔴 ¡CUIDADO! La imagen que enviaste contiene 
        texto sospechoso.
        📋 Texto detectado: "Las vacunas del covid matan..."
        👉 No compartas esta imagen.
```

---

### Semáforo de resultados

| Color | Significado | ¿Qué hacer? |
|---|---|---|
| 🟢 SEGURO | No encontramos señales de peligro | Puedes compartirlo con precaución |
| 🟡 PRECAUCIÓN | Tiene algunas señales sospechosas | Verifica en fuentes oficiales antes de compartir |
| 🔴 PELIGROSO | Alto riesgo de desinformación o phishing | No compartas ni hagas clic |
| 🔎 INCIERTO | No hay información suficiente | Consulta en andina.pe o rpp.pe |

---

### Comandos especiales del bot

| Escribe | Respuesta |
|---|---|
| `hola` | Mensaje de bienvenida con instrucciones |
| `ayuda` | Menú de ayuda completo |
| `?` | Menú de ayuda |

---

## PARTE 2: Extensión de Chrome

### Instalación

1. Ve a la **Chrome Web Store**
2. Busca **"Tucuy"**
3. Clic en **"Añadir a Chrome"**
4. Confirma los permisos
5. Verás el ícono de Tucuy (escudo azul) en la barra de herramientas

---

### Protección automática al navegar

Una vez instalada, la extensión **funciona sola** — no necesitas hacer nada. Al cargar cualquier página web, Tucuy revisa automáticamente todos los enlaces y resalta los peligrosos:

- **Borde rojo + ⚠️** = enlace peligroso, no hagas clic
- **Borde naranja + 🟡** = enlace sospechoso, verifica antes de entrar
- **Sin cambio** = enlace seguro

Al pasar el mouse sobre un enlace marcado, verás un cuadro explicando por qué es sospechoso.

---

### Verificar con clic derecho

Para analizar cualquier texto o enlace manualmente:

1. Selecciona el texto o haz clic derecho sobre un enlace
2. Elige **"🔍 Verificar con Tucuy"** del menú
3. Aparecerá un panel con el resultado en la esquina superior derecha

---

### Usar el popup de Tucuy

Haz clic en el ícono de Tucuy (escudo azul) en la barra de herramientas para abrir el panel de análisis manual. Tiene 4 pestañas:

#### Pestaña "Texto"
1. Pega el texto o noticia que quieres verificar
2. Clic en **"Analizar texto"**
3. Espera el resultado (puede tardar hasta 30 segundos la primera vez)

#### Pestaña "Enlace"
1. Pega la URL completa
2. Clic en **"Verificar enlace"**
3. El resultado es casi inmediato

#### Pestaña "Imagen"
1. Arrastra una imagen al cuadro, o clic para seleccionar un archivo
2. Clic en **"Analizar imagen"**
3. Tucuy extraerá el texto de la imagen y lo analizará

#### Pestaña "Todo"
Para analizar texto y URL al mismo tiempo:
1. Escribe el texto en el primer campo
2. Escribe la URL en el segundo campo
3. Clic en **"Analizar todo"**

---

### Indicador de estado del servidor

En la parte superior del popup verás un punto de color:
- 🟢 **Servidor activo** — todo funciona correctamente
- 🔴 **Servidor no disponible** — el servidor puede estar iniciando, espera 30 segundos y vuelve a intentar

---

## Fuentes de verificación que usa Tucuy

Cuando Tucuy dice que algo es falso, lo ha verificado usando:

- **Google Fact Check** — base de datos de verificaciones periodísticas de medios como ColombiaCheck, AFP Factual, Newtral, BBC
- **Google Safe Browsing** — lista de sitios maliciosos de Google
- **Lista de dominios peruanos** — comparación con BCP, BBVA, SUNAT, RENIEC, Yape y otros sitios oficiales del Perú

---

## Preguntas frecuentes

**¿Tucuy guarda mis mensajes?**  
No. Tucuy procesa el contenido en el momento y lo descarta inmediatamente. No almacena ningún dato personal tuyo.

**¿Por qué tarda a veces?**  
La primera consulta del día puede tardar hasta 30-60 segundos porque el servidor necesita "despertar". Las siguientes consultas son más rápidas.

**¿Qué hago si Tucuy dice que algo es seguro pero yo desconfío?**  
Puedes verificar también en:
- [andina.pe](https://andina.pe) — Agencia Andina oficial
- [rpp.pe](https://rpp.pe) — RPP Noticias
- [elcomercio.pe](https://elcomercio.pe) — El Comercio

**¿Funciona con cualquier imagen?**  
Funciona mejor con imágenes que tengan texto claro. Si la imagen es borrosa o tiene mucho ruido, puede que no extraiga el texto correctamente.

**¿Puedo usarlo en el celular?**  
La extensión Chrome solo funciona en computadoras. En el celular, usa el bot de WhatsApp.

---

## Contacto y soporte

Para reportar un error o sugerir mejoras, visita el repositorio del proyecto:  
[github.com/MeAnd17/anti-desinformacion](https://github.com/MeAnd17/anti-desinformacion)
