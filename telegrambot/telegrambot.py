import asyncio
import ssl
import os, logging
import aiomqtt
import json

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from functools import partial

# --- Configuración ---
logging.basicConfig(format='%(asctime)s - TelegramBot - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)


# === Variables de entorno ===
token = os.environ["TB_TOKEN"]
autorizados = [int(x) for x in os.environ["TB_AUTORIZADOS"].split(',')] if "TB_AUTORIZADOS" in os.environ else []
mqtt_host = os.environ["SERVIDOR"]
mqtt_port = int(os.environ.get("PUERTO_MQTTS", 8883))
mqtt_user = os.environ["MQTT_USR"]
mqtt_pass = os.environ["MQTT_PASS"]
topico_base = os.environ["TOPICO"]
# ============================

# === Variables Globales ===
ESPERANDO=""
temperatura=""
humedad=""
modo=""
periodo=""
setpoint=""
ultimo_mensaje_menu = None
# ==========================


# === Filtrar Usuarios Sin Autorización ===
async def sin_autorizacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("intento de conexión de: " + str(update.message.from_user.id))
    await context.bot.send_message(chat_id=update.effective_chat.id, text="no autorizado")
# =========================================


# === Bienvenida + inicio del teclado /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #logging.info(update)
    logging.info("se conectó: " + str(update.message.from_user.id))
    user = update.message.from_user
    nombre = user.first_name or ""
    apellido = user.last_name or "" 
    chat_id = update.effective_chat.id

    logging.info(f"Comando /start recibido de {nombre} {apellido} (ID: {user.id}) en el chat {chat_id}")
    kb = [["Comandar"],["Consultar"]]
    await context.bot.send_message(chat_id=chat_id, text=f"Bienvenido {nombre} {apellido}!", reply_markup=ReplyKeyboardMarkup(kb))
# =======================================

# === Manejar mensajes Comandar y Consultar ===
async def consultaocomando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ESPERANDO
    ESPERANDO=""

    # --- Elimina el menu InLineKeyboard si se envia otro comando de Comandar o Consultar---
    global ultimo_mensaje_menu
    try:
        if ultimo_mensaje_menu:
            await context.bot.edit_message_reply_markup(
                chat_id=update.effective_chat.id,
                message_id=ultimo_mensaje_menu,
                reply_markup=None  
            )
    except:
        pass  
    # --------------------------------------------------------------------------------------


    # --- Depende si es Comandar o Consultar crea diferentes InLineKeyboard ---
    if update.message.text == "Comandar":
        keyboard = [
            [InlineKeyboardButton("Setpoint", callback_data="comandar_setpoint")],
            [InlineKeyboardButton("Destello", callback_data="comandar_destello")],
            [InlineKeyboardButton("Modo", callback_data="comandar_modo")],
            [InlineKeyboardButton("Rele", callback_data="comandar_rele")],
            [InlineKeyboardButton("Periodo", callback_data="comandar_periodo")],
            [InlineKeyboardButton("Salir", callback_data="salir")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("Temperatura", callback_data="consultar_temp")],
            [InlineKeyboardButton("Humedad", callback_data="consultar_hum")],
            [InlineKeyboardButton("Estado", callback_data="consultar_estado")],
            [InlineKeyboardButton("Salir", callback_data="salir")]
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    mensaje = await update.message.reply_text("Estas son las opciones a elegir:", reply_markup=reply_markup)
    ultimo_mensaje_menu = mensaje.message_id

    # ------------------------------------------------------------------------


# === Manejar los callbacks de los InLineKeyboard ===
async def manejar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE,client):
    global temperatura, humedad, modo, periodo, setpoint, ESPERANDO

    query = update.callback_query
    await query.answer()

    match query.data:

        # --- Consultar ---
        case "consultar_temp":
            await query.edit_message_text(f"Temperatura: {temperatura}")

        case "consultar_hum":
            await query.edit_message_text(f"Humedad: {humedad}")

        case "consultar_estado":
            await query.edit_message_text(f"Temperatura: {temperatura}\nHumedad: {humedad}\nSetpoint: {setpoint}\nPeriodo: {periodo}\nModo: {modo}")
        # -----------------

        # --- Comandar ---
        case "comandar_setpoint":
            await query.edit_message_text("Ingresá el valor numérico para Setpoint:")
            ESPERANDO="setpoint"
        
        case "comandar_periodo":
            await query.edit_message_text("Ingresá el valor numérico para Periodo:")
            ESPERANDO="periodo"

        case "comandar_destello":
            await query.edit_message_text("Destellando...")
            await enviar_mensaje(client, topico_base + "/destello", "1")
            
        case "comandar_modo":
            keyboard = [
            [InlineKeyboardButton("Automatico", callback_data="modo_auto")],
            [InlineKeyboardButton("Manual", callback_data="modo_manual")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Estas son las opciones a elegir:", reply_markup=reply_markup)

        case "comandar_rele":
            if modo == "auto":
                await query.edit_message_text("No se puede cambiar el rele en modo Automatico")
            else:
                keyboard = [
                [InlineKeyboardButton("Encendido", callback_data="modo_true")],
                [InlineKeyboardButton("Apagado", callback_data="modo_false")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text("Estas son las opciones a elegir:", reply_markup=reply_markup)

        # ___ Opciones de Modo ___
        case "modo_auto":
            await query.edit_message_text("Modo automático activado.")
            await enviar_mensaje(client,topico_base + "/modo", "auto")
            modo="auto"

        case "modo_manual":
            await query.edit_message_text("Modo manual activado.")
            await enviar_mensaje(client,topico_base + "/modo", "manual")
            modo="manual"
        
        # ___ Opciones de Rele ___
        case "modo_true":
            await query.edit_message_text("Rele encendido.")
            await enviar_mensaje(client,topico_base + "/rele", "true")

        case "modo_false":
            await query.edit_message_text("Rele apagado.")
            await enviar_mensaje(client,topico_base + "/rele", "false")

        # ___ Caso general Salir ___
        case "salir":
            await query.edit_message_text("Saliendo...")
        # ----------------

# ===================================================


# === Si se solicita ingresar un Setpoint o un Periodo se hace aca ===
async def recibir_numero(update: Update, context: ContextTypes.DEFAULT_TYPE,client):
    global ESPERANDO, setpoint, periodo
    texto = update.message.text
    try:  
        valor = float(texto)
        if "setpoint" in ESPERANDO:
            await enviar_mensaje(client,topico_base + "/setpoint", valor)
            setpoint=valor
            await update.message.reply_text(f"Se ha cambiado el setpoint a {setpoint}°C")
            ESPERANDO=""
        if "periodo" in ESPERANDO:
            await enviar_mensaje(client,topico_base + "/periodo", valor)
            periodo=valor
            await update.message.reply_text(f"Se ha cambiado el pediodo a {periodo} segundos")
            ESPERANDO=""
    except ValueError:   
        await update.message.reply_text("Por favor, ingresá un número válido.")
        ESPERANDO=""
        return
# ====================================================================


# === Funcion General Para Enviar en MQTT ===
async def enviar_mensaje(client: aiomqtt.Client, topic, mensaje):
    try:
        await client.publish(topic, mensaje)
        logging.info(f"Mensaje enviado a {topic}: {mensaje}")
    except Exception as e:
        logging.info(f"Error al enviar mensaje a {topic}: {e}")
#============================================


# === Funcion que escucha al Brocker cuando el raspberry Infoma sobre el estado actual del
# Periodo, Setpoint, Modo, Temperatura y Humadad y lo guarda en variables para usarlos ===
async def EscucharTopicos(client, topico):
    global temperatura, humedad, modo, periodo, setpoint
    await client.subscribe(topico)
    log = logging.getLogger(topico)
    async for message in client.messages:
        log.info(f"Mensaje del Tópico [{topico}]: {message.payload.decode()}")
        try:
            datos = json.loads(message.payload)
            temperatura = datos.get("temperatura", "")
            humedad = datos.get("humedad", "")
            setpoint = datos.get("setpoint", "")
            periodo = datos.get("periodo", "")
            modo = datos.get("modo", "")
        except Exception as e:
            log.error(f"Error al decodificar mensaje: {e}")
# ========================================================================================


# === Funcion MAIN ===
async def main():
    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    application = Application.builder().token(token).build()

    
    try:
        logging.info(f"Intentando conectar a MQTT broker: {mqtt_host}:{mqtt_port} con TLS...")
        async with aiomqtt.Client(
            hostname=mqtt_host,
            port=mqtt_port,
            username=mqtt_user,
            password=mqtt_pass,
            tls_context=ssl_context
        ) as client:
            logging.info("Conectado exitosamente al broker MQTT.")

            # --- Para Escuchar en el Brocker ---
            asyncio.create_task(EscucharTopicos(client, topico_base))

            # --- Handlers ---
            application.add_handler(MessageHandler((~filters.User(autorizados)), sin_autorizacion))
            application.add_handler(CommandHandler('start', start))
            FuncCallback = partial(manejar_callback, client=client)
            application.add_handler(CallbackQueryHandler(FuncCallback))
            application.add_handler(MessageHandler(filters.Regex("^(Comandar|Consultar)$"), consultaocomando))
            handler_numeros = MessageHandler(filters.TEXT & filters.Regex(r'^-?\d+(\.\d+)?$'), partial(recibir_numero, client=client)) #Solo numeros y floats
            application.add_handler(handler_numeros)

            logging.info("Inicializando y arrancando bot de Telegram...")
            await application.initialize()
            await application.start()
            await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            logging.info("Bot de Telegram y cliente MQTT listos.")
            await asyncio.Event().wait()

    except (KeyboardInterrupt, asyncio.CancelledError):
        logging.info("\nInterrupción detectada (Ctrl+C o cancelación). Limpiando y cerrando...")

    finally:
        await application.updater.stop()
        await application.shutdown()
# ====================


if __name__ == "__main__":
    asyncio.run(main())