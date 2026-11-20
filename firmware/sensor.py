"""Read the BME280 sensor."""

import config
from bme280 import BME280
from machine import I2C, Pin

_i2c = I2C(0, sda=Pin(config.I2C_SDA), scl=Pin(config.I2C_SCL), freq=100_000)
_bme = BME280(i2c=_i2c, address=config.BME280_ADDRESS)


def read():
    """Return (temperature °C, humidity %, pressure hPa)."""
    temperature, pressure_pa, humidity = _bme.read_compensated_data()
    return temperature, humidity, pressure_pa / 100
