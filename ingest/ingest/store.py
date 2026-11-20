"""Store readings in PostgreSQL."""

import logging
import time

import psycopg

from ingest.messages import Reading

log = logging.getLogger(__name__)

INSERT_SQL = """
    INSERT INTO readings (device_id, ts, temperature_c, humidity_pct, pressure_hpa)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (device_id, ts) DO NOTHING
"""


def connect_with_retry(url: str, attempts: int = 30, delay_s: float = 2.0) -> psycopg.Connection:
    """Connect to the database, retrying while it starts up."""
    for attempt in range(1, attempts + 1):
        try:
            return psycopg.connect(url, autocommit=True)
        except psycopg.OperationalError as exc:
            if attempt == attempts:
                raise
            log.warning("database not ready (attempt %d/%d): %s", attempt, attempts, exc)
            time.sleep(delay_s)
    raise AssertionError("unreachable")


def insert_reading(conn: psycopg.Connection, reading: Reading) -> bool:
    """Insert one reading. Returns False if it was already stored (a resend)."""
    cur = conn.execute(
        INSERT_SQL,
        (
            reading.device_id,
            reading.ts,
            reading.temperature_c,
            reading.humidity_pct,
            reading.pressure_hpa,
        ),
    )
    return cur.rowcount == 1
