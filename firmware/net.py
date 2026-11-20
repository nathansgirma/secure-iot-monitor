"""Wi-Fi, clock and MQTT over TLS for the Pico W."""

import ssl
import time

import network
import ntptime
from umqtt.simple import MQTTClient

_wlan = network.WLAN(network.STA_IF)


def connect_wifi(ssid, password, timeout_s=15):
    _wlan.active(True)
    if _wlan.isconnected():
        return True
    _wlan.connect(ssid, password)
    start = time.ticks_ms()
    while not _wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) > timeout_s * 1000:
            return False
        time.sleep_ms(250)
    print("wifi connected:", _wlan.ifconfig()[0])
    return True


def wifi_connected():
    return _wlan.isconnected()


def sync_time():
    """Set the clock from NTP. Readings must not be sent before this works."""
    try:
        ntptime.settime()
    except OSError as exc:
        print("ntp failed:", exc)
        return False
    return time.gmtime()[0] >= 2024


class _FixedHostnameTLS:
    """umqtt passes the broker IP as the TLS server name, but the IP changes on a
    phone hotspot. Check the certificate against a fixed name instead."""

    def __init__(self, context, hostname):
        self._context = context
        self._hostname = hostname

    def wrap_socket(self, sock, server_hostname=None):
        return self._context.wrap_socket(sock, server_hostname=self._hostname)


def mqtt_connect(cfg):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_REQUIRED
    with open("certs/ca.der", "rb") as f:
        context.load_verify_locations(cadata=f.read())
    client = MQTTClient(
        cfg.DEVICE_ID,
        cfg.BROKER_IP,
        port=cfg.BROKER_PORT,
        user=cfg.DEVICE_ID,
        password=cfg.MQTT_PASSWORD,
        keepalive=60,
        ssl=_FixedHostnameTLS(context, cfg.TLS_HOSTNAME),
    )
    client.connect()
    print("mqtt connected to", cfg.BROKER_IP)
    return client
