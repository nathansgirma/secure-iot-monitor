# secure-iot-monitor

[![CI](https://github.com/nathansgirma/secure-iot-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/nathansgirma/secure-iot-monitor/actions/workflows/ci.yml)

A small, secure IoT monitoring system. A Raspberry Pi Pico W reads temperature, humidity and air pressure from a BME280 sensor and sends them over **encrypted MQTT** to a self-hosted stack: a Mosquitto broker, a Python ingest service, PostgreSQL and a Grafana dashboard. Everything on the server side runs in containers, and a simulator lets you run the whole system without any hardware.

![Grafana dashboard with temperature, humidity and pressure](docs/screenshot-dashboard.png)

*Dashboard with one hour of data from the simulator.*

> **Status:** the server side is finished and tested in CI. The Pico W firmware is written and compiles, but it has **not been tested on real hardware yet**.

## How it works

```mermaid
flowchart LR
    pico["Pico W + BME280<br/>(or the simulator)"] -- "MQTT over TLS :8883<br/>user + password" --> broker["Mosquitto<br/>TLS, ACL"]
    broker -- "sensors/+/readings" --> ingest["Ingest service<br/>(Python)"]
    ingest -- "validated rows" --> db[("PostgreSQL")]
    db -- "read-only user" --> grafana["Grafana<br/>localhost:3000"]
```

1. Every 10 seconds the device builds a JSON message and publishes it to `sensors/<device_id>/readings`:
   ```json
   {"device_id": "pico-01", "ts": "2026-12-20T14:05:00Z", "temperature_c": 21.4, "humidity_pct": 38.2, "pressure_hpa": 1012.6}
   ```
2. If Wi-Fi or the broker is down, the device keeps up to 100 readings in memory and sends them when the connection comes back.
3. The ingest service checks every message before storing it. It rejects broken JSON, missing fields, a device name that doesn't match the topic, clocks that are wrong, and values the sensor can't physically produce. A reading that is sent twice is stored once.
4. Grafana shows live graphs per device.

## Features

- **Security built in:** TLS on the only open port, a login for every device, an access list so a device can only publish as itself, a database that isn't reachable from the network, and a read-only database user for Grafana. See [SECURITY.md](SECURITY.md).
- **Reliable delivery:** the device buffers readings while offline. The broker keeps readings for the ingest service while it restarts, and everything reconnects by itself.
- **Tested:** unit tests, database integration tests and a full end-to-end test (simulator → broker → ingest → database) run in GitHub Actions on every push.
- **Runs without hardware:** `simulator/simulate.py` behaves like a Pico W.

## Quick start (no hardware needed)

Requirements: Linux with Podman (or Docker with Compose), Python 3.12+ and OpenSSL.

```bash
git clone https://github.com/nathansgirma/secure-iot-monitor.git
cd secure-iot-monitor

# 1. Random passwords in .env, TLS certificates, and the MQTT user for the ingest service
scripts/setup.sh

# 2. A login for the simulated device (prints its password)
scripts/add_device.sh pico-sim

# 3. Start the stack
podman compose up -d          # or: docker compose up -d

# 4. Send readings with the simulator
python3 -m venv .venv && .venv/bin/pip install -e "ingest[dev]"
.venv/bin/python simulator/simulate.py --device pico-sim --password <password from step 2>
```

Open <http://localhost:3000>, log in as `admin` with `GRAFANA_ADMIN_PASSWORD` from `.env`, and the **Sensors** dashboard shows the data.

## Running with a real Pico W

### Parts

- Raspberry Pi Pico WH (Pico W with headers)
- BME280 breakout board (I2C, 3.3 V). It must be a BME280, not a BMP280, which has no humidity sensor.
- Breadboard and jumper wires, plus a micro-USB data cable

### Wiring

| BME280 | Pico W |
|---|---|
| VIN | 3V3 (pin 36) |
| GND | GND (pin 38) |
| SDA | GP4 (pin 6) |
| SCL | GP5 (pin 7) |

### Network

The Pico W and the laptop join the same Wi-Fi. I use a phone hotspot. The Pico W only supports **2.4 GHz**; on an iPhone, turn on *Maximise Compatibility*. Traffic between the Pico and the laptop stays local.

The laptop's IP can change between hotspot sessions. The Pico connects to the IP in its config, but it checks the TLS certificate against the fixed name `iot-monitor.local`, so the certificate stays valid when the IP changes. Only the IP in `config.py` needs updating.

Allow MQTT through the laptop's firewall (Fedora):

```bash
sudo firewall-cmd --add-port=8883/tcp
sudo firewall-cmd --add-port=8883/tcp --permanent
```

### Flashing

```bash
scripts/add_device.sh pico-01                 # prints the device password
cp firmware/config.example.py firmware/config.py   # fill in Wi-Fi, laptop IP and password
mkdir -p firmware/certs && cp certs/ca.der firmware/certs/

# Install MicroPython (1.23 or newer) for the Pico W first, then:
pip install mpremote
mpremote mip install umqtt.simple
cd firmware && mpremote cp -r lib certs *.py : && mpremote reset
```

`mpremote repl` shows what the Pico is doing. The device waits for Wi-Fi and the correct time (NTP) before it sends anything, because readings with a wrong clock would be rejected.

## Tests

```bash
cd ingest && ../.venv/bin/pytest -m "not integration"     # message checks and service logic
cd simulator && ../.venv/bin/pytest                       # simulator output passes the checks
cd firmware && ../.venv/bin/pytest                        # buffer and message format (runs on a PC)
# Database tests need PostgreSQL, e.g.:
# DATABASE_URL=postgresql://postgres:test@127.0.0.1:55432/postgres pytest -m integration
```

GitHub Actions runs all of these, plus an end-to-end test that starts the whole stack with Docker Compose, sends readings with the simulator, checks that they reach the database, and checks that a client without a login is refused.

## Project layout

```
firmware/     MicroPython code for the Pico W (+ PC tests for its logic)
ingest/       Python ingest service, Containerfile and tests
broker/       Mosquitto config and access list
db/           database table and the read-only Grafana user
grafana/      provisioned data source and dashboard
simulator/    fake device, used for demos and CI
scripts/      setup, certificates, device logins
docs/         design, plan and screenshots
```

## About this project

I built this as a personal project during my IT studies at Metropolia UAS (Smart IoT Systems, IoT and Networks), to practise IoT, networking and security together. It was built with help from AI coding tools.

## Licence

MIT. `firmware/lib/bme280.py` is the MIT-licensed driver from [robert-hh/BME280](https://github.com/robert-hh/BME280), unchanged.
