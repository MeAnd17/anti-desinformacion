/**
 * index.js — Tucuy, bot de WhatsApp anti-desinformación
 * Usa Baileys (@whiskeysockets/baileys) en lugar de whatsapp-web.js
 *
 * Flujo:
 *   1. Usuario escribe "hola" → bienvenida + menú de opciones
 *   2. Usuario elige 1, 2 o 3 → bot le pide el contenido
 *   3. Usuario envía el contenido → bot analiza y responde
 *   4. Número inválido → bot pide que elija una opción correcta
 *
 * Solo responde mensajes directos (ignora grupos y broadcasts).
 */

const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
} = require("@whiskeysockets/baileys");

const pino    = require("pino");
const qrcode  = require("qrcode-terminal");
const path    = require("path");
const fs      = require("fs");
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

const MSG_PEDIR_URL    = `🔗 Perfecto. Pegame el enlace o URL que querés verificar.`;
const MSG_PEDIR_TEXTO  = `📝 Perfecto. Enviame el texto o frase que querés analizar.`;
const MSG_PEDIR_IMAGEN = `🖼️ Perfecto. Enviame la imagen o captura de pantalla que querés analizar.`;
const MSG_PROCESANDO   = "🔍 Analizando... un momento por favor.";

const MSG_ERROR = `😔 No pude analizar ese contenido. Intentá de nuevo.

Escribí *hola* para volver al menú principal.`;

const MSG_NO_ES_URL = `⚠️ Eso no parece un enlace válido.

Asegurate de que empiece con *https://* o *www.* y volvé a intentarlo.`;

const MSG_NO_ES_IMAGEN = `⚠️ No recibí una imagen.

Enviame una foto o captura de pantalla directamente en el chat.`;

const MSG_CONTINUAR = `¿Querés verificar otro contenido?

Respondé *sí* para continuar o *no* para terminar.`;

const MSG_DESPEDIDA = `¡Hasta luego! 👋

Fue un placer ayudarte. Si necesitás verificar algo más, escribime *hola* cuando quieras 🛡️`;

// Regex para detectar URLs en texto
const URL_REGEX =
  /(?:https?:\/\/|www\.)[a-zA-Z0-9\-._~:/?#[\]@!$&'()*+,;=%]+(?<![.,;:!?'"])/gi;

// Saludos que activan el menú
const SALUDOS = ["hola", "inicio", "start", "hi", "buenas", "buenos dias",
  "buenas tardes", "buenas noches", "menu", "menú", "ayuda", "help"];

// Estado de cada usuario: qué opción eligió
// { [jid]: "url" | "texto" | "imagen" | null }
const estadoUsuario = new Map();

// Directorio para guardar la sesión
const AUTH_DIR = path.join(__dirname, "auth_info_baileys");

// ---------------------------------------------------------------------------
// Función principal
// ---------------------------------------------------------------------------

async function startBot() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  console.log(`🔧 Usando WA v${version.join(".")}`);

  const sock = makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false,
    browser: ["Tucuy Bot", "Chrome", "1.0.0"],
    logger: pino({ level: "silent" }), // silenciar logs internos de Baileys
  });

  // Guardar credenciales cuando se actualicen
  sock.ev.on("creds.update", saveCreds);

  // Manejo de conexión
  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log("\n📱 Escaneá este QR con el WhatsApp del bot:");
      qrcode.generate(qr, { small: true });
      console.log("\nVe a WhatsApp → Dispositivos vinculados → Vincular dispositivo\n");
    }

    if (connection === "close") {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

      console.log(`⚠️  Conexión cerrada (código ${statusCode}). Reconectar: ${shouldReconnect}`);

      if (shouldReconnect) {
        console.log("🔄 Reconectando en 5 segundos...");
        setTimeout(startBot, 5000);
      } else {
        console.log("❌ Sesión cerrada. Borrá auth_info_baileys/ y volvé a escanear el QR.");
      }
    }

    if (connection === "open") {
      console.log("✅ Tucuy conectado y listo.");
      console.log("🛡️  Esperando mensajes directos...\n");
    }
  });

  // ---------------------------------------------------------------------------
  // Manejo de mensajes entrantes
  // ---------------------------------------------------------------------------

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;

    for (const msg of messages) {
      // Ignorar mensajes propios
      if (msg.key.fromMe) continue;

      // Ignorar grupos
      const jid = msg.key.remoteJid || "";
      if (jid.includes("@g.us")) continue;
      if (jid === "status@broadcast") continue;

      // Ignorar mensajes sin contenido
      const msgContent = msg.message;
      if (!msgContent) continue;

      // Extraer texto del mensaje
      const body = (
        msgContent.conversation ||
        msgContent.extendedTextMessage?.text ||
        msgContent.imageMessage?.caption ||
        ""
      ).trim();

      const bodyLower = body.toLowerCase();
      const sender = jid;

      console.log(`[${new Date().toLocaleTimeString()}] ${sender}: ${body.substring(0, 80)}${body.length > 80 ? "..." : ""}`);

      // Función helper para responder
      const reply = async (text) => {
        await sock.sendMessage(sender, { text }, { quoted: msg });
      };

      // Saludo → mostrar bienvenida y menú
      if (SALUDOS.includes(bodyLower)) {
        estadoUsuario.set(sender, null);
        await reply(MSG_BIENVENIDA);
        continue;
      }

      const estado = estadoUsuario.get(sender);

      // Usuario no ha saludado todavía
      if (estado === undefined) {
        estadoUsuario.set(sender, null);
        await reply(MSG_BIENVENIDA);
        continue;
      }

      // --- Esperando que elija una opción ---
      if (estado === null) {
        if (body === "1") {
          estadoUsuario.set(sender, "url");
          await reply(MSG_PEDIR_URL);
        } else if (body === "2") {
          estadoUsuario.set(sender, "texto");
          await reply(MSG_PEDIR_TEXTO);
        } else if (body === "3") {
          estadoUsuario.set(sender, "imagen");
          await reply(MSG_PEDIR_IMAGEN);
        } else {
          await reply(MSG_OPCION_INVALIDA);
        }
        continue;
      }

      // --- Esperando contenido ---

      if (estado === "url") {
        const urls = body.match(URL_REGEX) || [];
        if (urls.length === 0) {
          await reply(MSG_NO_ES_URL);
          continue;
        }
        await reply(MSG_PROCESANDO);
        const result = await handleUrl(urls[0]);
        await reply(result);
        estadoUsuario.set(sender, "continuar");
        await reply(MSG_CONTINUAR);
        continue;
      }

      if (estado === "texto") {
        if (!body) {
          await reply(MSG_PEDIR_TEXTO);
          continue;
        }
        await reply(MSG_PROCESANDO);
        const result = await handleTexto(body);
        await reply(result);
        estadoUsuario.set(sender, "continuar");
        await reply(MSG_CONTINUAR);
        continue;
      }

      if (estado === "imagen") {
        // Verificar que sea una imagen
        const isImage = !!(msgContent.imageMessage || msgContent.documentMessage);
        if (!isImage) {
          await reply(MSG_NO_ES_IMAGEN);
          continue;
        }

        await reply(MSG_PROCESANDO);
        const result = await handleImagen(sock, msg);
        await reply(result);
        estadoUsuario.set(sender, "continuar");
        await reply(MSG_CONTINUAR);
        continue;
      }

      // --- Respuesta a ¿querés continuar? ---
      if (estado === "continuar") {
        const resp = bodyLower;
        if (["si", "sí", "yes", "s", "claro", "dale", "ok"].includes(resp)) {
          estadoUsuario.set(sender, null);
          await reply(MSG_MENU);
        } else if (["no", "n", "nope", "nel"].includes(resp)) {
          estadoUsuario.delete(sender);
          await reply(MSG_DESPEDIDA);
        } else {
          await reply(`Por favor respondé *sí* o *no*.\n\n${MSG_CONTINUAR}`);
        }
        continue;
      }
    }
  });
}

// ---------------------------------------------------------------------------
// Handlers de análisis
// ---------------------------------------------------------------------------

async function handleUrl(url) {
  try {
    const result = await analyzeUrl(url);
    if (result.error) return result.message || MSG_ERROR;
    return result.formatted_message || formatFallback(result);
  } catch (err) {
    console.error("[Tucuy] Error en handleUrl:", err.message);
    return MSG_ERROR;
  }
}

async function handleTexto(text) {
  try {
    const result = await analyzeText(text);
    if (result.error) return result.message || MSG_ERROR;
    return result.formatted_message || formatFallback(result);
  } catch (err) {
    console.error("[Tucuy] Error en handleTexto:", err.message);
    return MSG_ERROR;
  }
}

async function handleImagen(sock, msg) {
  try {
    // Descargar imagen con Baileys (sin Puppeteer)
    const buffer = await downloadMediaMessage(
      msg,
      "buffer",
      {},
      { logger: console, reuploadRequest: sock.updateMediaMessage }
    );

    if (!buffer || buffer.length === 0) {
      return "😔 No pude descargar la imagen. ¿La podés reenviar?";
    }

    const msgContent = msg.message;
    const imageMsg   = msgContent.imageMessage || msgContent.documentMessage;
    const mimeType   = imageMsg?.mimetype || "image/jpeg";
    const extension  = mimeType.split("/")[1]?.split(";")[0] || "jpg";
    const filename   = `img_${Date.now()}.${extension}`;

    const result = await analyzeImage(buffer, mimeType, filename);

    if (result.error) return result.message || MSG_ERROR;

    if (result.ocr && !result.ocr.has_text) {
      return "🖼️ No encontré texto legible en la imagen.\n\nAsegurate de que sea clara y el texto esté visible.";
    }

    return result.formatted_message || formatFallback(result);
  } catch (err) {
    console.error("[Tucuy] Error en handleImagen:", err.message);
    return MSG_ERROR;
  }
}

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------

function formatFallback(result) {
  const risk = result.overall_risk_level || result.risk_level || "desconocido";
  const emojis = { alto: "🔴", medio: "🟡", bajo: "🟢" };
  const emoji  = emojis[risk] || "⚪";
  return (
    `${emoji} *Nivel de riesgo: ${risk.toUpperCase()}*\n\n` +
    "Si tenés dudas, consultá con alguien de confianza antes de compartir."
  );
}

// ---------------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------------

console.log("🚀 Iniciando Tucuy...");
console.log(`   Backend: ${process.env.BACKEND_URL || "https://tucuy-backend.onrender.com"}`);
console.log("   Esperando QR para vincular...\n");

startBot().catch(err => {
  console.error("❌ Error fatal al iniciar el bot:", err);
  process.exit(1);
});
