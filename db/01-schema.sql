-- One row per sensor reading.
CREATE TABLE IF NOT EXISTS readings (
    id            bigserial   PRIMARY KEY,
    device_id     text        NOT NULL,
    ts            timestamptz NOT NULL,
    temperature_c real        NOT NULL,
    humidity_pct  real        NOT NULL,
    pressure_hpa  real        NOT NULL,
    received_at   timestamptz NOT NULL DEFAULT now(),
    -- A device resends buffered readings after reconnecting.
    -- The same device can't have two readings at the same time,
    -- so resends are ignored instead of stored twice.
    -- This constraint also gives an index on (device_id, ts) for the dashboard.
    UNIQUE (device_id, ts)
);
