import json
import random
from datetime import UTC, datetime, timedelta

from ingest.messages import parse_reading
from simulate import make_reading


def test_simulated_reading_is_valid():
    rng = random.Random(1)
    start = datetime(2026, 12, 20, 14, 0, 0, tzinfo=UTC)
    for i in range(100):
        now = start + timedelta(seconds=10 * i)
        reading = make_reading("pico-sim", now, rng)
        parsed = parse_reading("sensors/pico-sim/readings", json.dumps(reading).encode(), now)
        assert parsed.device_id == "pico-sim"
        assert parsed.ts == now


def test_values_change_over_time():
    rng = random.Random(2)
    start = datetime(2026, 12, 20, 14, 0, 0, tzinfo=UTC)
    temps = {
        make_reading("pico-sim", start + timedelta(minutes=m), rng)["temperature_c"]
        for m in range(0, 60, 5)
    }
    assert len(temps) > 5
