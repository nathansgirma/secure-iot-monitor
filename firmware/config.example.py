# Copy this file to config.py and fill it in. config.py is not committed (it has passwords).

WIFI_SSID = "your-phone-hotspot"  # must be 2.4 GHz (iPhone: turn on "Maximise Compatibility")
WIFI_PASSWORD = ""

BROKER_IP = "172.20.10.2"  # the laptop's IP on the hotspot: run `ip -4 addr` on the laptop
BROKER_PORT = 8883
TLS_HOSTNAME = "iot-monitor.local"  # name in the server certificate; must not change

DEVICE_ID = "pico-01"  # also the MQTT username
MQTT_PASSWORD = ""  # printed by scripts/add_device.sh pico-01

INTERVAL_S = 10
BUFFER_SIZE = 100

I2C_SDA = 4  # GP4 (pin 6)
I2C_SCL = 5  # GP5 (pin 7)
BME280_ADDRESS = 0x76  # 0x77 on some boards; check with i2c.scan()
