import json
from datetime import UTC, datetime, timedelta

import pytest

from ingest.messages import InvalidReading, Reading, parse_reading

NOW = datetime(2026, 12, 20, 14, 10, 0, tzinfo=UTC)
TOPIC = "sensors/pico-01/readings"


def message(**changes):
    data = {
        "device_id": "pico-01",
        "ts": "2026-12-20T14:05:00Z",
        "temperature_c": 21.4,
        "humidity_pct": 38.2,
        "pressure_hpa": 1012.6,
    }
    data.update(changes)
    return json.dumps(data).encode()


def rejects(payload, topic=TOPIC):
    with pytest.raises(InvalidReading):
        parse_reading(topic, payload, NOW)


def test_valid_reading_parses():
    reading = parse_reading(TOPIC, message(), NOW)
    assert reading == Reading(
        device_id="pico-01",
        ts=datetime(2026, 12, 20, 14, 5, 0, tzinfo=UTC),
        temperature_c=21.4,
        humidity_pct=38.2,
        pressure_hpa=1012.6,
    )
    assert reading.ts.tzinfo == UTC


def test_integer_values_accepted():
    reading = parse_reading(TOPIC, message(temperature_c=21), NOW)
    assert reading.temperature_c == 21.0


def test_not_json_rejected():
    rejects(b"hello")


def test_not_utf8_rejected():
    rejects(b"\xff\xfe")


def test_json_not_object_rejected():
    rejects(b"[1, 2, 3]")


def test_missing_field_rejected():
    data = json.loads(message())
    del data["humidity_pct"]
    rejects(json.dumps(data).encode())


def test_string_number_rejected():
    rejects(message(temperature_c="21.4"))


def test_bool_rejected():
    rejects(message(temperature_c=True))


def test_topic_device_mismatch_rejected():
    rejects(message(), topic="sensors/pico-02/readings")


def test_bad_topic_rejected():
    rejects(message(), topic="sensors/pico-01/other")


def test_bad_device_id_rejected():
    rejects(message(device_id="Pico 01!"), topic="sensors/Pico 01!/readings")


def test_old_timestamp_rejected():
    rejects(message(ts="2000-01-01T00:00:12Z"))


def test_future_timestamp_rejected():
    future = (NOW + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rejects(message(ts=future))


def test_timestamp_without_z_rejected():
    rejects(message(ts="2026-12-20T14:05:00"))


def test_temperature_out_of_range_rejected():
    rejects(message(temperature_c=86.0))


def test_humidity_out_of_range_rejected():
    rejects(message(humidity_pct=100.5))


def test_pressure_out_of_range_rejected():
    rejects(message(pressure_hpa=1100.1))
