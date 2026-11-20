"""Build the JSON message that the ingest service expects."""


def build_message(device_id, gmtime, temperature_c, humidity_pct, pressure_hpa):
    year, month, day, hour, minute, second = gmtime[:6]
    ts = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z"
    return {
        "device_id": device_id,
        "ts": ts,
        "temperature_c": round(temperature_c, 2),
        "humidity_pct": round(humidity_pct, 2),
        "pressure_hpa": round(pressure_hpa, 2),
    }
