# Secure IoT Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Pico W + BME280 publishes readings over MQTT/TLS to a self-hosted stack (Mosquitto → Python ingest → PostgreSQL → Grafana) on Nate's laptop, with a simulator, tests and GitHub Actions, presentable by 10 Jan 2027.

**Architecture:** Four containers defined in one `compose.yaml` (run with `podman compose`, also Docker-compatible). Devices publish JSON to `sensors/<device_id>/readings`; the ingest service validates and inserts into one `readings` table; Grafana is provisioned from files. Device firmware is MicroPython; pure-logic firmware modules are tested on CPython.

**Tech Stack:** MicroPython ≥1.23 (Pico W), Python 3.12+, paho-mqtt 2.x, psycopg 3, pytest, ruff, Eclipse Mosquitto 2, PostgreSQL 16, Grafana OSS 11, OpenSSL, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-20-secure-iot-monitor-design.md`

## Global Constraints

- Repo: `github.com/nathansgirma/secure-iot-monitor`, public, MIT licence. Commit author: `Nathan S. Girma <227174284+nathansgirma@users.noreply.github.com>`.
- No cloud services.
- Never commit secrets: `.env`, `certs/`, `broker/passwd`, `firmware/config.py` are in `.gitignore`; commit `.env.example` and `firmware/config.example.py`.
- Topic: `sensors/<device_id>/readings`. Message JSON: `{"device_id": "pico-01", "ts": "2026-12-20T14:05:00Z", "temperature_c": 21.4, "humidity_pct": 38.2, "pressure_hpa": 1012.6}`.
- Publish interval 10 s. Offline buffer: last 100 readings in memory, oldest dropped.
- Only port 8883 (MQTT TLS) reachable from the network; PostgreSQL not published; Grafana bound to `127.0.0.1:3000`.
- TLS server certificate SAN: `DNS:iot-monitor.local, DNS:localhost`. Clients verify against hostname `iot-monitor.local` (simulator in CI may use `localhost`).
- Anonymous MQTT off; per-device username = device_id; ACL lets a device write only `sensors/<its id>/readings`; ingest user may only read `sensors/+/readings`.
- **Learning rule (anti-goal in spec):** every task ends with a walkthrough step where Nate explains the new part back. Steps marked **(Nate writes)** are typed by Nate, with the assistant reviewing.
- README states the project was built with help from AI coding tools.

## Review Focus

1. **Malformed payloads** (not JSON, not UTF-8, missing fields, strings instead of numbers) must be logged and dropped; the ingest service must never crash. → Task 1 tests, Task 3 test.
2. **Duplicate readings** when the Pico resends its buffer after a reconnect must not create duplicate rows. → Task 2 test (`UNIQUE (device_id, ts)`).
3. **Device clock not synced** (NTP failed, ts in 2000 or 1970) must be rejected, and the Pico must not publish before NTP succeeds. → Task 1 test, Task 7 step.
4. **Spoofing:** a device publishing a payload with another `device_id` than its topic is rejected by ingest, and publishing to another device's topic is blocked by the ACL. → Task 1 test, Task 4 verification.
5. **Broker or database restart** while running: ingest and simulator reconnect by themselves without manual restart. → Task 3 test (DB retry), Task 4 verification (broker restart).

---

### Task 1: Repo scaffold and message validation

**Files:**
- Create: `.gitignore`, `LICENSE`, `README.md` (stub), `.env.example`, `ingest/pyproject.toml`, `ingest/ingest/__init__.py`, `ingest/ingest/messages.py`
- Test: `ingest/tests/test_messages.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Reading: device_id: str; ts: datetime (tz-aware UTC); temperature_c: float; humidity_pct: float; pressure_hpa: float`
  - `class InvalidReading(ValueError)` — message says why.
  - `parse_reading(topic: str, payload: bytes, now: datetime) -> Reading` — raises `InvalidReading`.

Rules: topic must match `sensors/<id>/readings`; payload UTF-8 JSON object; all five fields present; numbers are int/float (not bool); `device_id` equals topic id and matches `^[a-z0-9-]{1,32}$`; ts ISO 8601 ending in `Z`; ts ≥ 2024-01-01T00:00:00Z and ≤ now + 5 min; temperature −40..85; humidity 0..100; pressure 300..1100 (BME280 ranges).

- [ ] **Step 1: Create repo on GitHub and scaffold** — `gh repo create nathansgirma/secure-iot-monitor --public --license mit`, clone, add `.gitignore` (entries above plus `__pycache__/`, `.venv/`), README stub with one-line description, `.env.example` with `MQTT_INGEST_PASSWORD=`, `POSTGRES_PASSWORD=`, `GRAFANA_ADMIN_PASSWORD=`. `pyproject.toml` with deps `paho-mqtt>=2,<3`, `psycopg[binary]>=3.1`, dev deps `pytest`, `ruff`.
- [ ] **Step 2: Write failing tests** in `test_messages.py`:
  - `test_valid_reading_parses` → fields equal the example message, `ts.tzinfo` is UTC
  - `test_not_json_rejected` (payload `b"hello"`), `test_not_utf8_rejected` (`b"\xff\xfe"`), `test_missing_field_rejected` (no `humidity_pct`), `test_string_number_rejected` (`"temperature_c": "21.4"`), `test_bool_rejected` (`true`)
  - `test_topic_device_mismatch_rejected` (topic `sensors/pico-02/readings`, payload id `pico-01`)
  - `test_bad_topic_rejected` (`sensors/pico-01/other`)
  - `test_old_timestamp_rejected` (`2000-01-01T00:00:12Z`), `test_future_timestamp_rejected` (now + 10 min), `test_timestamp_without_z_rejected`
  - `test_temperature_out_of_range_rejected` (86.0), `test_humidity_out_of_range_rejected` (100.5)
  - **(Nate writes)** `test_pressure_out_of_range_rejected` (1100.1) — plus the pressure rule in Step 4.
  Each rejection test: `with pytest.raises(InvalidReading): parse_reading(...)`.
- [ ] **Step 3: Run** `cd ingest && pytest -v` → FAIL (module not found).
- [ ] **Step 4: Implement** `parse_reading` and friends in `messages.py`. The pressure range check is **(Nate writes)**.
- [ ] **Step 5: Run** `pytest -v && ruff check .` → all PASS, no lint errors.
- [ ] **Step 6: Commit** `feat: message validation for sensor readings`.
- [ ] **Step 7: Walkthrough** — Nate explains why each rule exists (spoofing, clock, ranges).

### Task 2: Database schema and storage

**Files:**
- Create: `db/schema.sql`, `ingest/ingest/store.py`
- Test: `ingest/tests/test_store.py` (marked `@pytest.mark.integration`, needs `DATABASE_URL`)

**Interfaces:**
- Consumes: `Reading` (Task 1).
- Produces: `insert_reading(conn: psycopg.Connection, reading: Reading) -> bool` — True if inserted, False if duplicate. `connect_with_retry(url: str, attempts: int = 30, delay_s: float = 2.0) -> psycopg.Connection`.

- [ ] **Step 1: (Nate writes)** `db/schema.sql`: table `readings` (id bigserial PK, device_id text not null, ts timestamptz not null, temperature_c real, humidity_pct real, pressure_hpa real, received_at timestamptz not null default now(), `UNIQUE (device_id, ts)`), index on `(device_id, ts)` is covered by the unique constraint. Assistant reviews.
- [ ] **Step 2: Write failing tests:** `test_insert_then_select` (row appears with same values), `test_duplicate_returns_false_and_no_second_row` (insert same reading twice → second returns False, count = 1). Fixture applies `schema.sql` to a fresh schema per test.
- [ ] **Step 3: Start a throwaway DB and run** `podman run --rm -d -p 127.0.0.1:55432:5432 -e POSTGRES_PASSWORD=test postgres:16` then `DATABASE_URL=postgresql://postgres:test@127.0.0.1:55432/postgres pytest -m integration -v` → FAIL.
- [ ] **Step 4: Implement** `store.py` using `INSERT ... ON CONFLICT (device_id, ts) DO NOTHING` and `cursor.rowcount`.
- [ ] **Step 5: Run** the same command → PASS. Unit tests still pass with `pytest -m "not integration"`.
- [ ] **Step 6: Commit** `feat: readings table and storage`.
- [ ] **Step 7: Walkthrough** — Nate explains the unique constraint and why resends need it.

### Task 3: Ingest service

**Files:**
- Create: `ingest/ingest/main.py`, `ingest/Containerfile`
- Test: `ingest/tests/test_main.py`

**Interfaces:**
- Consumes: `parse_reading`, `InvalidReading`, `insert_reading`, `connect_with_retry`.
- Produces: `handle_message(topic: str, payload: bytes, store: Callable[[Reading], bool], now: Callable[[], datetime]) -> str` returning `"stored" | "duplicate" | "rejected"`; never raises for bad input. `main()` reads env `MQTT_HOST`, `MQTT_PORT` (8883), `MQTT_USER` (`ingest`), `MQTT_PASSWORD`, `MQTT_CA_FILE`, `MQTT_TLS_HOSTNAME` (`iot-monitor.local`), `DATABASE_URL`; subscribes `sensors/+/readings` QoS 1; logs one line per message.

- [ ] **Step 1: Write failing tests:** `test_valid_message_stored` (fake store returns True → "stored"), `test_duplicate` (store returns False → "duplicate"), `test_garbage_rejected_no_exception` (payload `b"\x00\xff"` → "rejected"), `test_store_error_does_not_crash` (store raises `psycopg.OperationalError` → returns "rejected" and logs; main loop reconnects DB on next message).
- [ ] **Step 2: Run** `pytest tests/test_main.py -v` → FAIL.
- [ ] **Step 3: Implement** `handle_message` and `main()`. TLS: `client.tls_set(ca_certs=...)`, connect to `MQTT_HOST` with `client.tls_insecure_set(False)`; when `MQTT_HOST` ≠ `MQTT_TLS_HOSTNAME`, wrap with an `ssl.SSLContext` whose `server_hostname` is `MQTT_TLS_HOSTNAME`. Use `loop_forever(retry_first_connection=True)` so broker restarts reconnect.
- [ ] **Step 4: Run** `pytest -m "not integration" -v && ruff check .` → PASS.
- [ ] **Step 5: Add `Containerfile`** (python:3.12-slim, install package, `CMD ["python","-m","ingest.main"]`); `podman build -t ingest ingest/` → succeeds.
- [ ] **Step 6: Commit** `feat: ingest service`.
- [ ] **Step 7: Walkthrough** — Nate traces one message from MQTT callback to database row.

### Task 4: Broker, certificates and the compose stack (with simulator)

**Files:**
- Create: `scripts/gen_certs.sh`, `scripts/add_device.sh`, `broker/mosquitto.conf`, `broker/acl`, `compose.yaml`, `simulator/simulate.py`
- Test: `simulator/test_simulate.py`

**Interfaces:**
- Consumes: ingest image (Task 3), `parse_reading` (Task 1, used in simulator test).
- Produces: `make_reading(device_id: str, now: datetime, rng: random.Random) -> dict` (realistic drifting values inside the valid ranges); CLI `python simulator/simulate.py --device pico-sim --password ... --host localhost --interval 10 [--count N]`. `scripts/add_device.sh <device_id>` prints a generated password and adds it to `broker/passwd`. `scripts/gen_certs.sh` writes `certs/ca.crt`, `certs/ca.key`, `certs/server.crt`, `certs/server.key` (SAN as in Global Constraints, 825-day validity).

- [ ] **Step 1: Failing test** `test_simulated_reading_is_valid`: 100 readings from `make_reading` all pass `parse_reading(f"sensors/{id}/readings", json.dumps(r).encode(), now)`.
- [ ] **Step 2: Run** → FAIL; **Step 3: implement** `simulate.py`; **Step 4: run** → PASS.
- [ ] **Step 5: Write broker config:** listener 8883 with cafile/certfile/keyfile, `allow_anonymous false`, `password_file`, `acl_file`. ACL: `user ingest` / `topic read sensors/+/readings`; `pattern write sensors/%u/readings`.
- [ ] **Step 6: Write `compose.yaml`:** services `mosquitto` (ports `8883:8883`), `postgres` (no published port, `schema.sql` mounted into `/docker-entrypoint-initdb.d/`, volume), `ingest` (env from `.env`, `MQTT_HOST=mosquitto`), `grafana` (`127.0.0.1:3000:3000`, admin password from `.env`). Restart policy `unless-stopped`.
- [ ] **Step 7: Verify end to end:**
  `./scripts/gen_certs.sh && ./scripts/add_device.sh pico-sim && podman compose up -d && python simulator/simulate.py --device pico-sim --password <pw> --host localhost --count 6 --interval 1`
  then `podman compose exec postgres psql -U postgres -c "select count(*) from readings"` → 6.
- [ ] **Step 8: Verify security:** `mosquitto_pub -h localhost -p 8883 --cafile certs/ca.crt -t sensors/pico-sim/readings -m x` (no user) → connection refused; simulator as `pico-sim` publishing to `sensors/pico-01/readings` → row count unchanged; `ss -tlnp` shows 3000 only on 127.0.0.1 and no 5432.
- [ ] **Step 9: Verify restart:** `podman compose restart mosquitto` while simulator runs → rows keep increasing within 30 s without restarting ingest or simulator.
- [ ] **Step 10: Commit** `feat: secure broker, compose stack and simulator`.
- [ ] **Step 11: Walkthrough** — Nate explains TLS, the CA, why the ACL uses `%u`, and why Postgres has no port.

### Task 5: Grafana dashboard

**Files:**
- Create: `grafana/provisioning/datasources/postgres.yaml`, `grafana/provisioning/dashboards/dashboards.yaml`, `grafana/dashboards/sensors.json`; modify `compose.yaml` (mounts).

**Interfaces:**
- Consumes: `readings` table.
- Produces: dashboard titled "Sensors" with a `device` variable (`select distinct device_id from readings`) and three time-series panels: temperature (°C), humidity (%), pressure (hPa); refresh 10 s; default range last 1 h. Datasource uses a read-only Postgres role `grafana` (created in `schema.sql`, `GRANT SELECT ON readings`).

- [ ] **Step 1: Write provisioning files and dashboard JSON.**
- [ ] **Step 2: Verify:** `podman compose up -d`, run simulator for 1 min, `curl -s -u admin:$GRAFANA_ADMIN_PASSWORD localhost:3000/api/search?query=Sensors` → one result; open the dashboard and see three moving graphs; take `docs/screenshot-dashboard.png`.
- [ ] **Step 3: Commit** `feat: provisioned Grafana dashboard`.
- [ ] **Step 4: Walkthrough** — Nate explains why Grafana gets a read-only user.

### Task 6: CI with GitHub Actions

**Files:**
- Create: `.github/workflows/ci.yml`, `simulator/e2e_check.sh`

**Interfaces:**
- Consumes: everything above.

Jobs: `lint-and-unit` (ruff + `pytest -m "not integration"` for ingest, simulator and `firmware/tests`); `integration` (Postgres 16 service container, `pytest -m integration`); `e2e` (`gen_certs.sh`, `add_device.sh pico-sim`, `docker compose up -d --build`, simulator `--count 6 --interval 1`, `e2e_check.sh` waits up to 60 s for `count(*) >= 6`, then `docker compose down -v`).

- [ ] **Step 1: Write workflow and `e2e_check.sh`.**
- [ ] **Step 2: Push and verify** `gh run watch` → all three jobs green.
- [ ] **Step 3: Break it on purpose** (change pressure max to 1000 locally, push to a branch) → `lint-and-unit` fails; revert.
- [ ] **Step 4: Commit** `ci: lint, unit, integration and end-to-end tests`; add CI badge to README.
- [ ] **Step 5: Walkthrough** — Nate explains what each job proves.

### Task 7: Pico W firmware

**Files:**
- Create: `firmware/main.py`, `firmware/sensor.py`, `firmware/net.py`, `firmware/buffer.py`, `firmware/config.example.py`, `firmware/lib/bme280.py` (third-party driver, keep its licence header), `firmware/certs/` (gitignored; holds `ca.crt` copy)
- Test: `firmware/tests/test_buffer.py` (CPython)

**Interfaces:**
- Produces: `class ReadingBuffer: __init__(maxlen=100); add(msg: dict) -> None; peek() -> dict | None; pop() -> None; __len__()`. `sensor.read() -> tuple[float, float, float]` (°C, %, hPa). `net.connect_wifi(ssid, password, timeout_s=15) -> bool`; `net.sync_time() -> bool`; `net.mqtt_connect(cfg) -> MQTTClient` (TLS, CA from `certs/ca.crt`, verifies hostname `iot-monitor.local` while connecting to `cfg.BROKER_IP`).
- `config.example.py`: `WIFI_SSID`, `WIFI_PASSWORD`, `BROKER_IP`, `BROKER_PORT=8883`, `TLS_HOSTNAME="iot-monitor.local"`, `DEVICE_ID="pico-01"`, `MQTT_PASSWORD`.

- [ ] **Step 1: Failing tests** `test_buffer_keeps_last_100` (add 150 → len 100, peek is #51), `test_pop_order_fifo`, `test_peek_empty_is_none`; run → FAIL; implement `buffer.py` (plain Python, no MicroPython-only imports); run → PASS.
- [ ] **Step 2: Hardware check: wiring** — BME280 VIN→3V3 (pin 36), GND→GND, SDA→GP4, SCL→GP5. Flash MicroPython ≥1.23 for Pico W. In REPL `machine.I2C(0, sda=Pin(4), scl=Pin(5)).scan()` → `[118]` or `[119]`.
- [ ] **Step 3: (Nate writes)** `sensor.read()` loop printing values every 2 s; breathing on the sensor raises humidity.
- [ ] **Step 4: Implement `net.py` and `main.py`:** connect Wi-Fi (hotspot, 2.4 GHz); `sync_time()` must succeed before any publish (retry every 10 s); every 10 s build the message, `buffer.add`, then while connected publish `peek()` with QoS 1 and `pop()` on success; on any network error drop the client and reconnect with backoff (5 s → 60 s max).
- [ ] **Step 5: Hardware check: live data** — `./scripts/add_device.sh pico-01`, laptop on the hotspot, set `BROKER_IP` to the laptop's hotspot IP (`ip -4 addr`), open firewall: `sudo firewall-cmd --add-port=8883/tcp` (and `--permanent`). Upload with `mpremote cp -r firmware/* :`. Grafana shows `pico-01` updating every 10 s.
- [ ] **Step 6: Hardware check: offline** — turn hotspot off for 2 min, on again → the gap fills in Grafana; `select count(*) ... group by ts having count(*)>1` → 0 rows (no duplicates).
- [ ] **Step 7: Commit** `feat: Pico W firmware with TLS and offline buffer`.
- [ ] **Step 8: Walkthrough** — Nate explains what happens when Wi-Fi drops and why the Pico waits for NTP.

### Task 8: Documentation, security write-up and demo

**Files:**
- Create: `SECURITY.md`, `docs/architecture.png` (or Mermaid in README), `docs/demo.gif`, `docs/demo.mp4`; rewrite `README.md`.

README sections: what it is (2 lines + GIF), architecture diagram, features, quick start with the simulator (no hardware), running with a real Pico (wiring table, hotspot note, updating `BROKER_IP`), security summary linking `SECURITY.md`, tests/CI, project layout, "Built with help from AI coding tools", licence. `SECURITY.md`: what is protected (TLS, per-device passwords, ACL, closed ports, read-only Grafana user, secrets out of Git), firewall commands, known limits (self-signed CA, passwords not client certificates, laptop as server, in-memory buffer lost on power loss).

- [ ] **Step 1: Record demo** (30–60 s): board on desk, breathe on sensor, Grafana reacts, hotspot off/on, gap fills. Make GIF (≤5 MB) + MP4 with ffmpeg.
- [ ] **Step 2: Write README and SECURITY.md** in plain English, honest claims only.
- [ ] **Step 3: Verify from scratch:** fresh clone in a temp dir, follow the README quick start exactly → dashboard shows simulator data within 10 minutes.
- [ ] **Step 4: Commit and push**; pin the repo on GitHub; check CI is green.
- [ ] **Step 5: Update the CV** (`/home/nateg/Documents/Personal/CV_Tech/`) and profile README with one honest project line.
- [ ] **Step 6: Final walkthrough** — Nate answers: why TLS, why an ACL, what happens when Wi-Fi drops, how a reading gets from sensor to graph.

## Schedule mapping

Tasks 1–6 need no hardware and can start 1 Dec (optional) or 14 Dec. Task 7 needs the parts (ordered by 1 Dec). Task 8 by 10 Jan. If late: cut the offline buffer (Task 7 Steps 4 partly and 6) and the GIF polish first; never cut security (Task 4 Steps 5–8), tests (Task 6) or the README.
