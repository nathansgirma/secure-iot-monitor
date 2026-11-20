"""Pico W main loop: read the sensor every INTERVAL_S seconds, buffer, send over MQTT/TLS."""

import json
import time

import config
import machine
import net
import sensor

from buffer import ReadingBuffer
from message import build_message

TOPIC = f"sensors/{config.DEVICE_ID}/readings"


def wait_for_clock():
    while not (net.connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD) and net.sync_time()):
        print("waiting for wifi and time...")
        time.sleep(10)
    print("clock set:", time.gmtime())


def run():
    buf = ReadingBuffer(config.BUFFER_SIZE)
    wait_for_clock()
    client = None
    backoff_s = 5
    next_try = time.ticks_ms()
    next_read = time.ticks_ms()

    while True:
        now = time.ticks_ms()

        if time.ticks_diff(now, next_read) >= 0:
            next_read = time.ticks_add(next_read, config.INTERVAL_S * 1000)
            try:
                temperature, humidity, pressure = sensor.read()
                buf.add(
                    build_message(config.DEVICE_ID, time.gmtime(), temperature, humidity, pressure)
                )
            except OSError as exc:
                print("sensor read failed:", exc)

        if client is None and time.ticks_diff(now, next_try) >= 0:
            try:
                if not net.wifi_connected() and not net.connect_wifi(
                    config.WIFI_SSID, config.WIFI_PASSWORD
                ):
                    raise OSError("wifi not available")
                client = net.mqtt_connect(config)
                backoff_s = 5
            except Exception as exc:  # OSError, MQTTException (bad password), MemoryError...
                print("connect failed, retry in", backoff_s, "s:", exc)
                next_try = time.ticks_add(now, backoff_s * 1000)
                backoff_s = min(backoff_s * 2, 60)

        while client is not None and len(buf):
            try:
                net.set_timeout(client, 10)
                client.publish(TOPIC, json.dumps(buf.peek()), qos=1)
                buf.pop()
            except Exception as exc:  # timeout, lost Wi-Fi, broken reply from the broker
                print("send failed, keeping", len(buf), "readings:", exc)
                try:
                    client.disconnect()
                except Exception:
                    pass
                client = None
                next_try = time.ticks_ms()

        time.sleep_ms(200)


try:
    run()
except Exception as exc:  # anything unexpected: log, wait, restart cleanly
    print("fatal:", exc)
    time.sleep(10)
    machine.reset()
