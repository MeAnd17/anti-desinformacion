/**
 * index.js — Tucuy, bot de WhatsApp anti-desinformación
 *
 * Flujo:
 *   1. Usuario escribe "hola" → bienvenida + menú de opciones
 *   2. Usuario elige 1, 2 o 3 → bot le pide el contenido
 *   3. Usuario envía el contenido → bot analiza y responde
 *   4. Número inválido → bot pide que elija una opción correcta
 *
 * Solo responde mensajes directos (ignora grupos y broadcasts).
 */

const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const { analyzeText, analyzeUrl, analyzeImage, analyzeFull } = require("./api_client");

// ---------------------------------------------------------------------------
// Mensajes predefinidos
// ---------------------------------------------------------------------------

const MSG_BIENVENIDA = `👋 ¡Hola! Soy *Tucuy* 🛡️

Estoy aquí para ayudarte a detectar noticias falsas, enlaces peligrosos e imágenes engañosas que circulan en internet.

Fui creado para proteger a los ciudadanos de Lima Metropolitana de la desinformación digital 🇵🇪

*¿Qué querés verificar?*

1️⃣ Un enlace o URL sospechosa
2️⃣ Un texto o frase que te generó dudas
3️⃣ Una imagen o captura de pantalla

Respondé con el número de la opción (1, 2 o 3).`;

const MSG_MENU = `*¿Qué querés verificar?*

1️⃣ Un enlace o URL sospechosa
2️⃣ Un texto o frase que te generó dudas
3️⃣ Una imagen o captura de pantalla

Respondé con el número de la opción (1, 2 o 3).`;

const MSG_OPCION_INVALIDA = `⚠️ Esa opción no es válida.

Por favor elegí una de estas opciones:

1️⃣ Enlace o URL
2️⃣ Texto o frase
3️⃣ Imagen o captura

Respondé solo con el número (1, 2 o 3).`;

const MSG_PEDIR_URL = `🔗 Perfecto. Pegame el enlace o URL que querés verificar.`;

const MSG_PEDIR_TEXTO = `📝 Perfecto. Enviame el texto o frase que querés analizar.`;

const MSG_PEDIR_IMAGEN = `🖼️ Perfecto. Enviame la imagen o captura de pantalla que querés analizar.`;

const MSG_PROCESANDO = "🔍 Analizando... un momento por favor.";

const MSG_ERROR = `😔 No pude analizar ese contenido. Intentá de nuevo.

Escribí *hola* para volver al menú principal.`;

const MSG_NO_ES_URL = `⚠️ Eso no parece un enlace válido.

Asegurate de que empiece con *https://* o *www.* y volvé a intentarlo.`;

const MSG_NO_ES_IMAGEN = `⚠️ No recibí una imagen.

Enviame una foto o captura de pantalla directamente en el chat.`;

// Regex para detectar URLs en texto
const URL_REGEX =
  /(?:https?:\/\/|www\.)[a-zA-Z0-9\-._~:/?#[\]@!$&'()*+,;=%]+(?<![.,;:!?'"])/gi;

// Saludos que activan el menú
const SALUDOS = ["hola", "inicio", "start", "hi", "buenas", "buenos dias",
  "buenas tardes", "buenas noches", "menu", "menú", "ayuda", "help"];

// Estado de cada usuario: qué opción eligió y está esperando contenido
// { [sender]: "url" | "texto" | "imagen" | null }
const estadoUsuario = new Map();

// ---------------------------------------------------------------------------
// Cliente WhatsApp
// ---------------------------------------------------------------------------

const client = new Client({
  authStrategy: new LocalAuth({
    clientId: "tucuy-bot",
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
  console.log("✅ Tucuy conectado y listo.");
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
  // Solo mensajes directos
  if (message.fromMe) return;
  if (message.from.includes("@g.us")) return;
  if (message.from === "status@broadcast") return;
  if (message.broadcast) return;
  if (message.type === "e2e_notification") return;
  if (message.type === "notification_template") return;
  if (message.type === "call_log") return;

  const sender = message.from;
  const body = (message.body || "").trim();
  const bodyLower = body.toLowerCase();

  console.log(`[${new Date().toLocaleTimeString()}] ${sender}: ${body.substring(0, 80)}${body.length > 80 ? "..." : ""}`);

  // --- Saludo → mostrar bienvenida y menú ---
  if (SALUDOS.includes(bodyLower)) {
    estadoUsuario.set(sender, null);
    await safeReply(message, MSG_BIENVENIDA);
    return;
  }

  const estado = estadoUsuario.get(sender);

  // --- Usuario no ha saludado todavía ---
  if (estado === undefined) {
    estadoUsuario.set(sender, null);
    await safeReply(message, MSG_BIENVENIDA);
    return;
  }

  // --- Esperando que elija una opción del menú ---
  if (estado === null) {
    if (body === "1") {
      estadoUsuario.set(sender, "url");
      await safeReply(message, MSG_PEDIR_URL);
    } else if (body === "2") {
      estadoUsuario.set(sender, "texto");
      await safeReply(message, MSG_PEDIR_TEXTO);
    } else if (body === "3") {
      estadoUsuario.set(sender, "imagen");
      await safeReply(message, MSG_PEDIR_IMAGEN);
    } else {
      await safeReply(message, MSG_OPCION_INVALIDA);
    }
    return;
  }

  // --- Esperando contenido según la opción elegida ---

  if (estado === "url") {
    const urls = body.match(URL_REGEX) || [];
    if (urls.length === 0) {
      await safeReply(message, MSG_NO_ES_URL);
      return;
    }
    await handleUrl(message, urls[0]);
    estadoUsuario.set(sender, null);
    await safeReply(message, MSG_MENU);
    return;
  }

  if (estado === "texto") {
    if (!body) {
      await safeReply(message, MSG_PEDIR_TEXTO);
      return;
    }
    await handleTexto(message, body);
    estadoUsuario.set(sender, null);
    await safeReply(message, MSG_MENU);
    return;
  }

  if (estado === "imagen") {
    if (!message.hasMedia || !["image", "document"].includes(message.type)) {
      await safeReply(message, MSG_NO_ES_IMAGEN);
      return;
    }
    await handleImagen(message);
    estadoUsuario.set(sender, null);
    await safeReply(message, MSG_MENU);
    return;
  }
});

// ---------------------------------------------------------------------------
// Handlers por tipo de contenido
// ---------------------------------------------------------------------------

async function safeReply(message, text) {
  try {
    await message.reply(text);
  } catch (err) {
    console.error("[Tucuy] Error al responder:", err.message);
  }
}

async function handleUrl(message, url) {
  await safeReply(message, MSG_PROCESANDO);
  try {
    const result = await analyzeUrl(url);
    if (result.error) {
      await safeReply(message, result.message || MSG_ERROR);
      return;
    }
    await safeReply(message, result.formatted_message || formatFallback(result));
  } catch (err) {
    console.error("[Tucuy] Error en handleUrl:", err.message);
    await safeReply(message, MSG_ERROR);
  }
}

async function handleTexto(message, text) {
  await safeReply(message, MSG_PROCESANDO);
  try {
    const result = await analyzeText(text);
    if (result.error) {
      await safeReply(message, result.message || MSG_ERROR);
      return;
    }
    await safeReply(message, result.formatted_message || formatFallback(result));
  } catch (err) {
    console.error("[Tucuy] Error en handleTexto:", err.message);
    await safeReply(message, MSG_ERROR);
  }
}

async function handleImagen(message) {
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
        "🖼️ No encontré texto legible en la imagen.\n\n" +
        "Asegurate de que sea clara y el texto esté visible."
      );
      return;
    }

    await safeReply(message, result.formatted_message || formatFallback(result));
  } catch (err) {
    console.error("[Tucuy] Error en handleImagen:", err.message);
    await safeReply(message, MSG_ERROR);
  }
}

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------

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

console.log("🚀 Iniciando Tucuy...");
console.log(`   Backend: ${process.env.BACKEND_URL || "http://localhost:8000"}`);
console.log("   Esperando QR para vincular...\n");

client.initialize();
