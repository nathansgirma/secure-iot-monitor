"""Parse and validate sensor readings that arrive over MQTT."""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

TOPIC_RE = re.compile(r"^sensors/([^/]+)/readings$")
DEVICE_ID_RE = re.compile(r"^[a-z0-9-]{1,32}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

OLDEST_TS = datetime(2024, 1, 1, tzinfo=UTC)
MAX_CLOCK_AHEAD = timedelta(minutes=5)

# Physical limits of the BME280 sensor.
RANGES = {
    "temperature_c": (-40.0, 85.0),
    "humidity_pct": (0.0, 100.0),
    "pressure_hpa": (300.0, 1100.0),
}


class InvalidReading(ValueError):
    """The message is not a valid sensor reading. The message says why."""


@dataclass(frozen=True)
class Reading:
    device_id: str
    ts: datetime
    temperature_c: float
    humidity_pct: float
    pressure_hpa: float


def parse_reading(topic: str, payload: bytes, now: datetime) -> Reading:
    match = TOPIC_RE.match(topic)
    if not match:
        raise InvalidReading(f"unexpected topic {topic!r}")
    topic_device = match.group(1)

    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidReading(f"payload is not UTF-8 JSON: {exc}") from None
    if not isinstance(data, dict):
        raise InvalidReading("payload is not a JSON object")

    missing = [f for f in ("device_id", "ts", *RANGES) if f not in data]
    if missing:
        raise InvalidReading(f"missing fields: {', '.join(missing)}")

    device_id = data["device_id"]
    if not isinstance(device_id, str) or not DEVICE_ID_RE.match(device_id):
        raise InvalidReading(f"bad device_id {device_id!r}")
    if device_id != topic_device:
        raise InvalidReading(f"device_id {device_id!r} does not match topic {topic_device!r}")

    ts = _parse_ts(data["ts"])
    if ts < OLDEST_TS:
        raise InvalidReading(f"timestamp {data['ts']} is too old; device clock not synced?")
    if ts > now + MAX_CLOCK_AHEAD:
        raise InvalidReading(f"timestamp {data['ts']} is in the future")

    values = {}
    for field, (low, high) in RANGES.items():
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidReading(f"{field} must be a number")
        if not low <= value <= high:
            raise InvalidReading(f"{field}={value} outside {low}..{high}")
        values[field] = float(value)

    return Reading(device_id=device_id, ts=ts, **values)


def _parse_ts(value) -> datetime:
    if not isinstance(value, str) or not TS_RE.match(value):
        raise InvalidReading(f"ts must be ISO 8601 UTC ending in Z, got {value!r}")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:  # right shape but impossible date, e.g. 30 February
        raise InvalidReading(f"ts {value!r} is not a real date: {exc}") from None
