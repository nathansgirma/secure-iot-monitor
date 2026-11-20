"""Fake Pico W: publishes realistic readings so the system can run without hardware."""

import argparse
import json
import math
import random
import ssl
import sys
import threading
import time
from datetime import UTC, datetime

import paho.mqtt.client as mqtt


def make_reading(device_id: str, now: datetime, rng: random.Random) -> dict:
    """A plausible indoor reading that drifts slowly over the day."""
    t = now.timestamp()
    temperature = 21.0 + 1.5 * math.sin(t / 900) + rng.uniform(-0.1, 0.1)
    humidity = 40.0 + 5.0 * math.sin(t / 1300 + 1.0) + rng.uniform(-0.5, 0.5)
    pressure = 1012.0 + 3.0 * math.sin(t / 7200) + rng.uniform(-0.2, 0.2)
    return {
        "device_id": device_id,
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "temperature_c": round(temperature, 2),
        "humidity_pct": round(humidity, 2),
        "pressure_hpa": round(pressure, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="pico-sim")
    parser.add_argument("--password", required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8883)
    parser.add_argument("--cafile", default="certs/ca.crt")
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--count", type=int, default=0, help="stop after N readings (0 = forever)")
    parser.add_argument("--topic", help="override the topic (for testing the ACL)")
    args = parser.parse_args()

    topic = args.topic or f"sensors/{args.device}/readings"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=args.device)
    client.username_pw_set(args.device, args.password)
    client.tls_set(ca_certs=args.cafile, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    connected = threading.Event()
    client.on_connect = lambda c, u, f, rc, p: connected.set() if not rc.is_failure else None
    client.on_disconnect = lambda c, u, f, rc, p: connected.clear()
    client.connect_async(args.host, args.port)
    client.loop_start()

    rng = random.Random()
    sent = 0
    try:
        while args.count == 0 or sent < args.count:
            if not connected.wait(timeout=30):
                print("waiting for broker connection...", file=sys.stderr, flush=True)
                continue
            now = datetime.now(UTC).replace(microsecond=0)
            reading = make_reading(args.device, now, rng)
            try:
                info = client.publish(topic, json.dumps(reading), qos=1)
                info.wait_for_publish(timeout=30)
            except (RuntimeError, ValueError) as exc:
                print(f"publish failed, will retry: {exc}", file=sys.stderr, flush=True)
                continue
            if info.is_published():
                sent += 1
                print(f"sent {reading}", flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
