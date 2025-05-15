from mqtt_as import MQTTClient
from mqtt_local import config
import uasyncio as asyncio
import ujson
import machine
from machine import Pin
import dht


#-----------------------Obtencion del id del dispositivo---------------------------------------

id = ""
for b in machine.unique_id():
  id += "{:02X}".format(b)
print(id)


#----------------------------------Guardado Local----------------------------------------------

ARCHIVO = "config.json"

# Valores predeterminados
config_default = {
    "setpoint": 25,
    "periodo": 10,
    "modo": 1,
    "rele": False
}

# Funcion para cargar valores al archivo local
def cargar_config():
    try:
        with open(ARCHIVO, "r") as f:
            return ujson.load(f)
    except OSError:
         #Si no existe el archivo crea un con los valores predeterminados
        guardar_config(config_default) 
        return config_default

#Guardar configuración en el archivo
def guardar_config(config):
    with open(ARCHIVO, "w") as f:
        ujson.dump(config, f)

#Funcion llamada al momento de escribir, guarda en local los valores
def escribir(param,valor):
    config = cargar_config()
    if "setpoint" in param:
            config["setpoint"] = valor
    if "periodo" in param:
            config["periodo"] = valor
    if "modo" in param:
            config["modo"] = valor
    if "rele" in param:
            config["rele"] = valor
    guardar_config(config)


#Al iniciar, carga los valores locales a una variable
Parametros = cargar_config()
print("Parametros cargados")

#-------------------------------- Sensor -----------------------------------------------
d = dht.DHT11(Pin(15)) 

def sensor():
    d.measure()
    return d.temperature(), d.humidity()

#---------------------------------- Relé ------------------------------------------------
Pin_Rele = Pin(6,Pin.OUT)

def comparar_temps(setpoint):
    temperatura,humedad = sensor()
    configuracion = cargar_config()
    if configuracion["modo"] is 0:
        Pin_Rele.value(setpoint>temperatura)
    return

def rele_manual(rele):
     configuracion = cargar_config()
     if configuracion["modo"] is 1:
          Pin_Rele.value(not rele)
          print("rele cambiado")

#--------------------------------------Destello----------------------------------------------
Pin_LED = Pin("LED",Pin.OUT)

async def destellar(tiempo):
    for _ in range(tiempo*5):
        Pin_LED.value(True)
        await asyncio.sleep(tiempo/(2*tiempo*5))
        Pin_LED.value(False)
        await asyncio.sleep(tiempo/(2*tiempo*5))

#----------------------------------Mensaje de Error-----------------------------

async def mensaje_error():
    await client.publish(id, "Ingresaste un valor erroneo. Prueba:\n\tModo: 1-Manual 0-Automatico\n\tDestello: tiempo en segundos o nada\n\tPeriodo: valor numerico en segundos\n\tSetpoint: valor numerico (usar punto para los decimales)\n\trele: true o false (para encender o apagar en modo manual)", qos = 1)

#-------------------------------- MQTTA ---------------------------------------

#Funcion para formar el mensaje que se transmite
def formar_mensaje():
    configuracion = cargar_config()
    var_temp,var_humedad = sensor()
    var_setpoint = configuracion["setpoint"]
    var_periodo = configuracion["periodo"]
    var_modo = configuracion["modo"]
    mensaje = ujson.dumps({"temperatura": var_temp, "humedad": var_humedad, "setpoint": var_setpoint, "periodo": var_periodo, "modo": var_modo})
    return mensaje
     

SERVER = config['server']

#Funcion de recepcion de mensajes
def sub_cb(topic, msg, retained):
    topic = topic.decode()
    msg = msg.decode()

    print(f"Topic = {topic} | Mensaje = {msg} | Retained = {retained}")

    if topic.endswith("periodo"):
        try:
            periodo = int(msg)
            print(f"Nuevo periodo: {periodo}")
            escribir("periodo",periodo)
        except ValueError:
            asyncio.create_task(mensaje_error())

    elif topic.endswith("setpoint"):
        try:
            setpoint = float(msg)
            print(f"Nuevo setpoint: {setpoint}")
            escribir("setpoint",setpoint)
        except ValueError:
            asyncio.create_task(mensaje_error())

    elif topic.endswith("modo"):
        try:
            modo = int(msg)
            print(f"Nuevo modo: {modo}")
            escribir("modo",modo)
        except ValueError:
            asyncio.create_task(mensaje_error())

    elif topic.endswith("destello"):
        try:
            tiempo = int(msg)
        except ValueError:
            tiempo = 3
        print("Destello")
        asyncio.create_task(destellar(tiempo))
        

    elif topic.endswith("rele"):
        try:
            rele = msg.lower() == "true"
            print(f"Nuevo estado del relé: {rele}")
            escribir("rele",rele)
            rele_manual(rele)
        except Exception:
            asyncio.create_task(mensaje_error())

async def conn_han(client):
    await client.subscribe(id+"/periodo", 1)
    await client.subscribe(id+"/setpoint", 1)
    await client.subscribe(id+"/modo", 1)
    await client.subscribe(id+"/destello", 1)
    await client.subscribe(id+"/rele", 1)

#---------------------------------- Wifi ------------------------------------------
async def wifi_han(state):
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)


#--------------------------------------MAIN-----------------------------------------

async def main(client):
    await client.connect()
    await asyncio.sleep(2)  # Give broker time
    while True:
        await client.publish(id, formar_mensaje(), qos = 1)
        configuracion = cargar_config()
        comparar_temps(configuracion["setpoint"])
        await asyncio.sleep(configuracion["periodo"])  #Periodo antes de volver a transmitir

# Define configuration
config['subs_cb'] = sub_cb
config['server'] = SERVER
config['connect_coro'] = conn_han
config['wifi_coro'] = wifi_han
config['ssl'] = True

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)
try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()