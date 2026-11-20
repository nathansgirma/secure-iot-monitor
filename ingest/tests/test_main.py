import json
import logging
from datetime import UTC, datetime

import psycopg

from ingest.main import DbStore, handle_message

NOW = datetime(2026, 12, 20, 14, 10, 0, tzinfo=UTC)
TOPIC = "sensors/pico-01/readings"
GOOD = json.dumps(
    {
        "device_id": "pico-01",
        "ts": "2026-12-20T14:05:00Z",
        "temperature_c": 21.4,
        "humidity_pct": 38.2,
        "pressure_hpa": 1012.6,
    }
).encode()


def now():
    return NOW


def test_valid_message_stored():
    stored = []

    def store(reading):
        stored.append(reading)
        return True

    assert handle_message(TOPIC, GOOD, store, now) == "stored"
    assert stored[0].device_id == "pico-01"


def test_duplicate():
    assert handle_message(TOPIC, GOOD, lambda r: False, now) == "duplicate"


def test_garbage_rejected_no_exception(caplog):
    calls = []
    with caplog.at_level(logging.WARNING):
        result = handle_message(TOPIC, b"\x00\xff", calls.append, now)
    assert result == "rejected"
    assert calls == []
    assert "rejected" in caplog.text


def test_store_error_does_not_crash(caplog):
    def broken_store(reading):
        raise psycopg.OperationalError("connection lost")

    with caplog.at_level(logging.ERROR):
        result = handle_message(TOPIC, GOOD, broken_store, now)
    assert result == "rejected"
    assert "connection lost" in caplog.text


class FakeConn:
    def __init__(self, fail):
        self.fail = fail
        self.closed = False

    def close(self):
        self.closed = True


def test_db_store_reconnects_after_error():
    conns = [FakeConn(fail=True), FakeConn(fail=False)]
    made = []

    def connect():
        conn = conns[len(made)]
        made.append(conn)
        return conn

    def insert(conn, reading):
        if conn.fail:
            raise psycopg.OperationalError("server closed the connection")
        return True

    store = DbStore(connect, insert)
    try:
        store("reading-1")
    except psycopg.OperationalError:
        pass
    assert store("reading-2") is True
    assert len(made) == 2
    assert conns[0].closed
