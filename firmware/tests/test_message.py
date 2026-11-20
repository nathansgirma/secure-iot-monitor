import json
from datetime import UTC, datetime

from ingest.messages import parse_reading
from message import build_message

# time.gmtime() tuple on the Pico: (year, month, day, hour, minute, second, weekday, yearday)
GMTIME = (2026, 12, 20, 14, 5, 7, 6, 354)


def test_message_format():
    msg = build_message("pico-01", GMTIME, 21.456, 38.21, 1012.63)
    assert msg == {
        "device_id": "pico-01",
        "ts": "2026-12-20T14:05:07Z",
        "temperature_c": 21.46,
        "humidity_pct": 38.21,
        "pressure_hpa": 1012.63,
    }


def test_message_accepted_by_ingest():
    msg = build_message("pico-01", GMTIME, 21.4, 38.2, 1012.6)
    now = datetime(2026, 12, 20, 14, 6, 0, tzinfo=UTC)
    reading = parse_reading("sensors/pico-01/readings", json.dumps(msg).encode(), now)
    assert reading.device_id == "pico-01"
