import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest

from ingest.messages import Reading
from ingest.store import connect_with_retry, insert_reading

pytestmark = pytest.mark.integration

SCHEMA = Path(__file__).resolve().parents[2] / "db" / "01-schema.sql"

READING = Reading(
    device_id="pico-01",
    ts=datetime(2026, 12, 20, 14, 5, 0, tzinfo=UTC),
    temperature_c=21.5,
    humidity_pct=38.25,
    pressure_hpa=1012.5,
)


@pytest.fixture
def conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    conn = connect_with_retry(url, attempts=5, delay_s=1.0)
    conn.execute("DROP TABLE IF EXISTS readings")
    conn.execute(SCHEMA.read_text())
    yield conn
    conn.close()


def count(conn):
    return conn.execute("SELECT count(*) FROM readings").fetchone()[0]


def test_insert_then_select(conn):
    assert insert_reading(conn, READING) is True
    row = conn.execute(
        "SELECT device_id, ts, temperature_c, humidity_pct, pressure_hpa FROM readings"
    ).fetchone()
    assert row == ("pico-01", READING.ts, 21.5, 38.25, 1012.5)


def test_duplicate_returns_false_and_no_second_row(conn):
    assert insert_reading(conn, READING) is True
    assert insert_reading(conn, READING) is False
    assert count(conn) == 1


def test_connect_with_retry_gives_up():
    with pytest.raises(psycopg.OperationalError):
        connect_with_retry(
            "postgresql://nobody:x@127.0.0.1:1/none?connect_timeout=1", attempts=2, delay_s=0
        )
