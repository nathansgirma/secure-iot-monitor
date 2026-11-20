"""Ingest service: MQTT readings in, PostgreSQL rows out."""

import logging
import os
import signal
import ssl
from collections.abc import Callable
from datetime import UTC, datetime

import paho.mqtt.client as mqtt
import psycopg

from ingest.messages import InvalidReading, Reading, parse_reading
from ingest.store import connect_with_retry, insert_reading

log = logging.getLogger("ingest")

SUBSCRIBE_TOPIC = "sensors/+/readings"


def handle_message(
    topic: str,
    payload: bytes,
    store: Callable[[Reading], bool],
    now: Callable[[], datetime],
) -> str:
    """Validate and store one message. Never raises; returns what happened."""
    try:
        reading = parse_reading(topic, payload, now())
    except InvalidReading as exc:
        log.warning("rejected message on %s: %s", topic, exc)
        return "rejected"
    try:
        inserted = store(reading)
    except psycopg.Error as exc:
        log.error("could not store reading from %s: %s", reading.device_id, exc)
        return "rejected"
    if not inserted:
        log.info("duplicate reading from %s at %s", reading.device_id, reading.ts.isoformat())
        return "duplicate"
    log.info("stored reading from %s at %s", reading.device_id, reading.ts.isoformat())
    return "stored"


class DbStore:
    """Calls insert with a live connection; reconnects after a database error."""

    def __init__(self, connect: Callable[[], object], insert: Callable[[object, Reading], bool]):
        self._connect = connect
        self._insert = insert
        self._conn = None

    def __call__(self, reading: Reading) -> bool:
        if self._conn is None:
            self._conn = self._connect()
        try:
            return self._insert(self._conn, reading)
        except psycopg.OperationalError:
            try:
                self._conn.close()
            finally:
                self._conn = None
            raise


def utc_now() -> datetime:
    return datetime.now(UTC)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    host = os.environ.get("MQTT_HOST", "iot-monitor.local")
    port = int(os.environ.get("MQTT_PORT", "8883"))
    database_url = os.environ["DATABASE_URL"]

    store = DbStore(lambda: connect_with_retry(database_url), insert_reading)

    # Persistent session: the broker keeps QoS 1 readings for us while we are offline.
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ingest", clean_session=False)
    client.username_pw_set(os.environ.get("MQTT_USER", "ingest"), os.environ["MQTT_PASSWORD"])
    client.tls_set(ca_certs=os.environ["MQTT_CA_FILE"], tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("MQTT connect failed: %s", reason_code)
            return
        log.info("connected to %s:%d, subscribing to %s", host, port, SUBSCRIBE_TOPIC)
        client.subscribe(SUBSCRIBE_TOPIC, qos=1)

    def on_message(client, userdata, msg):
        handle_message(msg.topic, msg.payload, store, utc_now)

    client.on_connect = on_connect
    client.on_message = on_message
    # Stop cleanly when the container is stopped (python as PID 1 ignores SIGTERM otherwise).
    signal.signal(signal.SIGTERM, lambda signum, frame: client.disconnect())
    client.connect_async(host, port)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
