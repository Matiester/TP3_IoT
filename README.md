# Bot de Telegram + MQTT (aiomqtt)

Este codigo se complementa con el primer TP e implementa un bot de Telegram que se comunica con la RaspBerry a traves de MQTT sobre TLS. Permite **consultar y comandar** estados como temperatura, humedad, setpoint, periodo, modo y relé.

## Funcionalidades

- Menú interactivo con botones `InlineKeyboard` y `ReplyKeyboard`.
- Consulta de temperatura, humedad y estado (temperatura, humedad, setpoint, periodo, modo y relé recibidos del MQTT).
- Comando de:
  - Setpoint (valor numérico flotante en grados)
  - Periodo (valor numérico en segundos)
  - Modo (automático/manual)
  - Relé (encendido/apagado en modo manual)
  - Destello del LED integrado en la RaspBerry
- Control de acceso por lista de usuarios autorizados.

## Requisitos

- Python 3.10+
- Variables de entorno configuradas
- Broker MQTT con TLS habilitado
- Certificados válidos
- Librerias: aiomqtt y python-telegram-bot
- Una RaspBerry corriendo el Codigo en /CoodigoRaspberry con su respectivo DHT11 o DHT22 y el modulo de Relé

## Variables de entorno necesarias

```env
TB_TOKEN=tu_token_de_telegram
TB_AUTORIZADOS=123456789,987654321
SERVIDOR=broker.ejemplo.com
PUERTO_MQTTS=8883
MQTT_USR=usuario
MQTT_PASS=contraseña
TOPICO=ID_del_Raspy
