/**
 * index.js — Bot de WhatsApp anti-desinformación
 *
 * El bot funciona como un chat directo. El usuario lo busca por número,
 * le escribe, y le manda lo que quiere analizar:
 *   - Texto plano   → módulo NLP (fake news)
 *   - URL           → módulo Levenshtein + URL checker
 *   - Texto + URL   → análisis combinado (/analyze/full)
 *   - Imagen        → OCR + NLP
 *   - Mensaje reenviado → analiza el contenido del reenvío
 *
 * Solo responde mensajes directos (ignora grupos y broadcasts).
 */

const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const { analyzeText, analyzeUrl, analyzeImage, analyzeFull } = require("./api_client");

// ---------------------------------------------------------------------------
// Mensajes predefinidos
// ---------------------------------------------------------------------------

const MSG_BIENVENIDA = `👋 ¡Hola! Soy el bot *AntiDesinformación* 🛡️

Te ayudo a verificar si un mensaje, enlace o imagen es confiable.

*¿Qué me podés enviar?*
🔗 Un enlace o URL sospechosa
📝 Un texto o noticia que quieras verificar
🖼️ Una imagen o captura de pantalla
📨 Un mensaje reenviado que te generó dudas

Simplemente mandámelo y te digo qué encontré.

Escribí *ayuda* si tenés preguntas.`;

const MSG_AYUDA = `🆘 *¿Cómo usar el bot?*

1. *Enviá un enlace* → verifico si es seguro o sospechoso
2. *Enviá un texto* → analizo si puede ser desinformación
3. *Enviá una imagen* → extraigo el texto y lo analizo
4. *Reenviá un mensaje* → analizo el contenido que te enviaron

*Comandos:*
• *hola* → ver mensaje de bienvenida
• *ayuda* → ver estas instrucciones

🛡️ Tu seguridad digital es nuestra prioridad.`;

const MSG_PROCESANDO = "🔍 Analizando... un momento.";

const MSG_ERROR = `😔 No pude analizar ese contenido.

Intentá de nuevo o escribí *ayuda* para ver cómo usarme.`;

const MSG_SIN_CONTENIDO = `🤔 No encontré contenido para analizar.

Podés enviarme:
• Un enlace (https://...)
• Un texto o noticia
• Una imagen o captura`;

// Regex para detectar URLs en texto
const URL_REGEX =
  /(?:https?:\/\/|www\.)[a-zA-Z0-9\-._~:/?#[\]@!$&'()*+,;=%]+(?<![.,;:!?'"])/gi;

// Usuarios que ya recibieron la bienvenida (en memoria, se resetea al reiniciar)
const usuariosConocidos = new Set();

// ---------------------------------------------------------------------------
// Cliente WhatsApp
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
  console.log("\n📱 Escaneá este QR con el WhatsApp del bot:");
  qrcode.generate(qr, { small: true });
  console.log("\nVe a WhatsApp → Dispositivos vinculados → Vincular dispositivo\n");
});

client.on("ready", () => {
  console.log("✅ Bot conectado y listo.");
  console.log("🛡️  Esperando mensajes directos...\n");
});

client.on("auth_failure", (msg) => {
  console.error("❌ Falló la autenticación:", msg);
  console.error("   Borrá la carpeta .wwebjs_auth/ y volvé a escanear el QR.");
});

client.on("disconnected", (reason) => {
  console.warn("⚠️  Bot desconectado:", reason);
});

// ---------------------------------------------------------------------------
// Manejo de mensajes entrantes
// ---------------------------------------------------------------------------

client.on("message", async (message) => {
  // Solo mensajes directos — ignorar todo lo demás
  if (message.fromMe) return;
  if (message.from.includes("@g.us")) return;        // grupos
  if (message.from === "status@broadcast") return;   // estados
  if (message.broadcast) return;                     // broadcasts
  if (message.type === "e2e_notification") return;
  if (message.type === "notification_template") return;
  if (message.type === "call_log") return;

  const sender = message.from;
  const body = (message.body || "").trim();

  console.log(`[${new Date().toLocaleTimeString()}] Mensaje de ${sender}: ${body.substring(0, 80)}${body.length > 80 ? "..." : ""}`);

  // Bienvenida al primer mensaje
  if (!usuariosConocidos.has(sender)) {
    usuariosConocidos.add(sender);
    await safeReply(message, MSG_BIENVENIDA);
    // Si el primer mensaje ya tiene algo analizable, seguimos procesando
    if (!body && !message.hasMedia) return;
  }

  // Comandos especiales
  const bodyLower = body.toLowerCase();

  if (["hola", "inicio", "start", "hi", "buenas", "buenos dias", "buenas tardes", "buenas noches"].includes(bodyLower)) {
    await safeReply(message, MSG_BIENVENIDA);
    return;
  }

  if (["ayuda", "help", "?", "menu", "menú", "comandos"].includes(bodyLower)) {
    await safeReply(message, MSG_AYUDA);
    return;
  }

  // Imagen adjunta
  if (message.hasMedia && ["image", "document"].includes(message.type)) {
    await handleImageMessage(message);
    return;
  }

  // Mensaje reenviado — usar el cuerpo del reenvío
  if (message.hasQuotedMsg || message._data?.isForwarded) {
    if (body) {
      await handleTextMessage(message, body);
      return;
    }
  }

  // Texto o URL
  if (body) {
    await handleTextMessage(message, body);
    return;
  }

  // No hay contenido reconocible
  await safeReply(message, MSG_SIN_CONTENIDO);
});

// ---------------------------------------------------------------------------
// Handlers por tipo de contenido
// ---------------------------------------------------------------------------

/**
 * Responde un mensaje de forma segura sin crashear el proceso.
 */
async function safeReply(message, text) {
  try {
    await message.reply(text);
  } catch (err) {
    console.error("[Bot] Error al responder:", err.message);
  }
}

/**
 * Analiza texto. Si contiene URL usa el análisis combinado,
 * si no, usa solo NLP.
 */
async function handleTextMessage(message, text) {
  const urls = text.match(URL_REGEX) || [];

  await safeReply(message, MSG_PROCESANDO);

  try {
    let result;

    if (urls.length > 0) {
      // Texto con URL → análisis combinado
      result = await analyzeFull({ text, url: urls[0] });
    } else {
      // Solo texto → NLP
      result = await analyzeText(text);
    }

    if (result.error) {
      await safeReply(message, result.message || MSG_ERROR);
      return;
    }

    const respuesta = result.formatted_message || formatFallback(result);
    await safeReply(message, respuesta);

  } catch (err) {
    console.error("[Bot] Error en handleTextMessage:", err.message);
    await safeReply(message, MSG_ERROR);
  }
}

/**
 * Descarga y analiza una imagen usando OCR + NLP.
 */
async function handleImageMessage(message) {
  await safeReply(message, MSG_PROCESANDO);

  try {
    const media = await message.downloadMedia();

    if (!media || !media.data) {
      await safeReply(message, "😔 No pude descargar la imagen. ¿La podés reenviar?");
      return;
    }

    const imageBuffer = Buffer.from(media.data, "base64");
    const mimeType = media.mimetype || "image/jpeg";
    const extension = mimeType.split("/")[1] || "jpg";
    const filename = `img_${Date.now()}.${extension}`;

    const result = await analyzeImage(imageBuffer, mimeType, filename);

    if (result.error) {
      await safeReply(message, result.message || MSG_ERROR);
      return;
    }

    if (result.ocr && !result.ocr.has_text) {
      await safeReply(message,
        "🖼️ Recibí tu imagen pero no encontré texto legible.\n\n" +
        "Asegurate de que la imagen sea clara y el texto esté visible."
      );
      return;
    }

    const respuesta = result.formatted_message || formatFallback(result);
    await safeReply(message, respuesta);

  } catch (err) {
    console.error("[Bot] Error en handleImageMessage:", err.message);
    await safeReply(message, MSG_ERROR);
  }
}

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------

/**
 * Formato de fallback si el backend no devuelve formatted_message.
 */
function formatFallback(result) {
  const risk = result.overall_risk_level || result.risk_level || "desconocido";
  const emojis = { alto: "🔴", medio: "🟡", bajo: "🟢" };
  const emoji = emojis[risk] || "⚪";

  return (
    `${emoji} *Nivel de riesgo: ${risk.toUpperCase()}*\n\n` +
    "Si tenés dudas, consultá con alguien de confianza antes de compartir."
  );
}

// ---------------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------------

console.log("🚀 Iniciando Bot AntiDesinformación...");
console.log(`   Backend: ${process.env.BACKEND_URL || "http://localhost:8000"}`);
console.log("   Esperando QR para vincular...\n");

client.initialize();
