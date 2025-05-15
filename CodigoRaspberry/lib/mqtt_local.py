# mqtt_local.py Local configuration for mqtt_as demo programs.
from sys import platform, implementation
from mqtt_as import config
from settings import SSID, password, BROKER

config['server'] = BROKER  # Change to suit
config['ssid'] = SSID
config['wifi_pw'] = password

