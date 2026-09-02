/**
 * index.js — Bot de WhatsApp anti-desinformación
 *
 * Conecta a WhatsApp mediante whatsapp-web.js y analiza mensajes entrantes:
 *   - Texto plano   → módulo NLP (BETO fake news)
 *   - URLs          → módulo Levenshtein (typosquatting)
 *   - Texto + URL   → análisis combinado (/analyze/full)
 *   - Imágenes      → módulo OCR + NLP
 *
 * Responde con mensajes amigables formateados para adultos mayores.
 */

const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const { analyzeText, analyzeUrl, analyzeImage, analyzeFull } = require("./api_client");

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

const MENSAJE_BIENVENIDA = `¡Hola! 👋 Soy tu asistente *AntiDesinformación* 🛡️

Puedo ayudarte a verificar si un mensaje, enlace o imagen es seguro.

*¿Cómo usarme?*
📝 *Texto:* Envíame el mensaje que quieres verificar
🔗 *Enlace:* Pega el enlace sospechoso
🖼️ *Imagen:* Envíame la captura de pantalla

Desarrollado para proteger a los ciudadanos de Lima Metropolitana 🇵🇪`;

const MENSAJE_PROCESANDO = "🔍 Analizando el contenido... un momento por favor.";

const MENSAJE_ERROR_GENERICO =
  "😔 Tuve un problema al analizar ese contenido. " +
  "¿Puedes intentarlo de nuevo? Si el problema continúa, " +
  "escribe *ayuda* para ver las instrucciones.";

const MENSAJE_AYUDA = `🆘 *Instrucciones de uso:*

1️⃣ Envía cualquier texto sospechoso y te digo si es una noticia falsa
2️⃣ Pega un enlace (URL) y verifico si es seguro
3️⃣ Envía una imagen o captura de pantalla y extraigo el texto para analizarlo

*Comandos especiales:*
• Escribe *ayuda* para ver este menú
• Escribe *hola* para el mensaje de bienvenida

🛡️ Tu seguridad digital es nuestra prioridad.`;

// Regex para detectar URLs en un texto
const URL_REGEX =
  /(?:https?:\/\/|www\.)[a-zA-Z0-9\-._~:/?#[\]@!$&'()*+,;=%]+(?<![.,;:!?'"])/gi;

// Set de números que ya recibieron el mensaje de bienvenida (en memoria)
const usuariosConocidos = new Set();

// ---------------------------------------------------------------------------
// Inicialización del cliente WhatsApp
// ---------------------------------------------------------------------------

const client = new Client({
  authStrategy: new LocalAuth({
    clientId: "anti-desinformacion-bot",
  }),
  puppeteer: {
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-accelerated-2d-canvas",
      "--no-first-run",
      "--no-zygote",
      "--disable-gpu",
    ],
  },
});

// ---------------------------------------------------------------------------
// Eventos del cliente
// ---------------------------------------------------------------------------

client.on("qr", (qr) => {
  console.log("\n[Bot] Escanea este código QR con tu WhatsApp:");
  qrcode.generate(qr, { small: true });
  console.log("\nVe a WhatsApp → Dispositivos vinculados → Vincular dispositivo\n");
});

client.on("ready", () => {
  console.log("✅ [Bot] Cliente WhatsApp listo y conectado.");
  console.log("🛡️  Bot AntiDesinformación activo — esperando mensajes...\n");
});

client.on("auth_failure", (msg) => {
  console.error("❌ [Bot] Falló la autenticación:", msg);
  console.error("   Elimina la carpeta .wwebjs_auth/ y vuelve a escanear el QR.");
});

client.on("disconnected", (reason) => {
  console.warn("⚠️  [Bot] Desconectado:", reason);
});

// ---------------------------------------------------------------------------
// Manejo de mensajes entrantes
// ---------------------------------------------------------------------------

client.on("message", async (message) => {
  // Ignorar mensajes del propio bot
  if (message.fromMe) return;
  // Ignorar grupos
  if (message.from.includes("@g.us")) return;
  // Ignorar estados de WhatsApp (status@broadcast y cualquier broadcast)
  if (message.from === "status@broadcast") return;
  if (message.broadcast) return;
  // Ignorar mensajes de sistema o notificaciones
  if (message.type === "e2e_notification") return;
  if (message.type === "notification_template") return;
  if (message.type === "call_log") return;

  const sender = message.from;
  const body = (message.body || "").trim();

  console.log(`[Bot] Mensaje de ${sender}: ${body.substring(0, 80)}${body.length > 80 ? "..." : ""}`);

  // --- Bienvenida al primer contacto ---
  if (!usuariosConocidos.has(sender)) {
    usuariosConocidos.add(sender);
    await safeReply(message, MENSAJE_BIENVENIDA);
    // Si el primer mensaje ya tiene contenido analizable, continuar procesando
    if (!body) return;
  }

  // --- Comandos especiales ---
  const bodyLower = body.toLowerCase();
  if (bodyLower === "hola" || bodyLower === "inicio" || bodyLower === "start") {
    await safeReply(message, MENSAJE_BIENVENIDA);
    return;
  }
  if (bodyLower === "ayuda" || bodyLower === "help" || bodyLower === "?") {
    await safeReply(message, MENSAJE_AYUDA);
    return;
  }

  // --- Imagen adjunta ---
  if (message.hasMedia) {
    await handleImageMessage(message);
    return;
  }

  // --- Texto con o sin URL ---
  if (body) {
    await handleTextMessage(message, body);
    return;
  }
});

// ---------------------------------------------------------------------------
// Handlers por tipo de contenido
// ---------------------------------------------------------------------------

/**
 * Wrapper seguro para message.reply() que evita crashes del proceso.
 */
async function safeReply(message, text) {
  try {
    await message.reply(text);
  } catch (err) {
    console.error("[Bot] Error al enviar respuesta:", err.message);
  }
}

/**
 * Analiza un mensaje de texto. Si contiene URLs, usa el endpoint /analyze/full
 * para combinar análisis NLP + Levenshtein simultáneamente.
 */
async function handleTextMessage(message, text) {
  const urlsEncontradas = text.match(URL_REGEX) || [];

  try {
    let result;

    if (urlsEncontradas.length > 0) {
      // Hay texto + URL → análisis combinado
      const primaryUrl = urlsEncontradas[0];
      result = await analyzeFull({ text, url: primaryUrl });
    } else {
      // Solo texto → NLP
      result = await analyzeText(text);
    }

    if (result.error) {
      await safeReply(message, result.message || MENSAJE_ERROR_GENERICO);
      return;
    }

    const respuesta = result.formatted_message || formatFallback(result);
    await safeReply(message, respuesta);

  } catch (err) {
    console.error("[Bot] Error en handleTextMessage:", err.message);
    await safeReply(message, MENSAJE_ERROR_GENERICO);
  }
}

/**
 * Descarga la imagen adjunta, la envía al backend para OCR + NLP
 * y responde con el análisis.
 */
async function handleImageMessage(message) {
  try {
    await safeReply(message, MENSAJE_PROCESANDO);

    const media = await message.downloadMedia();

    if (!media || !media.data) {
      await safeReply(message, "😔 No pude descargar la imagen. ¿Puedes intentar enviarla de nuevo?");
      return;
    }

    // Convertir base64 a Buffer
    const imageBuffer = Buffer.from(media.data, "base64");
    const mimeType = media.mimetype || "image/jpeg";
    const extension = mimeType.split("/")[1] || "jpg";
    const filename = `image_${Date.now()}.${extension}`;

    const result = await analyzeImage(imageBuffer, mimeType, filename);

    if (result.error) {
      await safeReply(message, result.message || MENSAJE_ERROR_GENERICO);
      return;
    }

    // Si la imagen no tenía texto legible
    if (result.ocr && !result.ocr.has_text) {
      await safeReply(message,
        "🖼️ Recibí tu imagen pero no encontré texto legible en ella.\n\n" +
        "💡 Si la imagen tiene texto, asegúrate de que sea clara y bien iluminada."
      );
      return;
    }

    const respuesta = result.formatted_message || formatFallback(result);
    await safeReply(message, respuesta);

  } catch (err) {
    console.error("[Bot] Error en handleImageMessage:", err.message);
    await safeReply(message, MENSAJE_ERROR_GENERICO);
  }
}

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------

/**
 * Formateador de fallback por si el backend no retorna formatted_message.
 */
function formatFallback(result) {
  const risk =
    result.overall_risk_level ||
    result.risk_level ||
    "desconocido";

  const emojis = { alto: "🔴", medio: "🟡", bajo: "🟢" };
  const emoji = emojis[risk] || "⚪";

  return (
    `${emoji} Nivel de riesgo: *${risk.toUpperCase()}*\n\n` +
    "👉 Consulta a un familiar de confianza si tienes dudas."
  );
}

// ---------------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------------

console.log("🚀 Iniciando Bot AntiDesinformación...");
console.log(`   Backend: ${process.env.BACKEND_URL || "http://localhost:8000"}`);
console.log("   Esperando código QR...\n");

client.initialize();
