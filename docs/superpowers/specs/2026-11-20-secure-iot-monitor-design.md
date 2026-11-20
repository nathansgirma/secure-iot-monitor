# Secure IoT Monitor: design

Date: 20 November 2026
Owner: Nathan S. Girma (Nate)
Build window: 14 Dec 2026 – 17 Jan 2027. Must be presentable by **10 Jan 2027**.

## Why this project exists

Nate is a second-year IT student at Metropolia (Smart IoT Systems, IoT and Networks). He wants a summer 2027 trainee job or internship in Finland. His GitHub has one real project (DontStress, a group project where he built the Wi-Fi/MQTT/Kubios networking) and coursework. He needs one solo project that recruiters can see, run and ask him about.

The project was chosen from real Finnish summer-trainee ads (Konecranes IoT, Kempower cloud, Danfoss embedded, Konecranes/UPM cybersecurity, Wärtsilä, Visma, Nokia). The skills those ads repeat are: IoT devices and communication protocols, Linux, SQL, Git/GitHub, CI/CD, APIs and security. Applications for summer 2027 close in **February 2027**; several open in early January. That is why the project must be presentable by 10 Jan.

Success means: by 10 Jan, a public GitHub repo with a working system, a clear README, an architecture diagram, a demo video, and automated tests running in GitHub Actions. Nate can explain every part in an interview and can add it to his CV (`/home/nateg/Documents/Personal/CV_Tech/`).

## What it is

A small, secure sensor monitoring system:

```
Pico W + BME280 sensor
   │  MQTT over TLS (port 8883), per-device username/password
   ▼
Laptop (Fedora), containers run with Podman:
   Mosquitto broker ──► ingest service (Nate's Python) ──► PostgreSQL ──► Grafana dashboard
```

1. A Raspberry Pi Pico W reads temperature, humidity and air pressure from a BME280 sensor every 10 seconds.
2. It publishes each reading as JSON to an MQTT topic over TLS. If the broker or Wi-Fi is down, it keeps readings in a small buffer and sends them when the connection comes back.
3. A Python ingest service, written by Nate, subscribes to the topic, validates each message, and writes good readings into PostgreSQL. Bad messages are logged and rejected.
4. Grafana reads PostgreSQL and shows live graphs per device.
5. GitHub Actions runs the ingest service's tests and a linter on every push.

## Goals

- End-to-end working system with live data on a dashboard.
- Real security, not just a mention: TLS encryption, per-device credentials, topic access control, closed ports, no secrets in Git.
- Nate's own code at both ends: device firmware and the ingest service.
- Automated tests and CI in GitHub Actions.
- Easy for a recruiter to understand in 30 seconds and for an engineer to run in 10 minutes with the simulator, no hardware needed.

## Non-goals

- No cloud services (no AWS, Azure etc.). Nate will study AWS in his third year.
- No custom web frontend or mobile app; Grafana is the UI.
- No fleet management. The system must support more than one device in its data model, but only one physical device is required.
- No machine learning.

## Anti-goals (would make it a failure even if it works)

- **Nate cannot explain it.** Nate's choice (20 Nov): the assistant builds most of it and Nate reviews and learns each step. To make that real: every milestone ends with a short walkthrough where Nate explains the new part back in his own words; Nate writes a few small pieces himself (the BME280 reading loop, the SQL schema, one validation rule and its test); and before 10 Jan he must be able to answer "why TLS", "why an ACL", "what happens when Wi-Fi drops", "how does a reading get from the sensor to the graph". The README says the project was built with help from AI coding tools (assistant's recommendation; Nate can change this).
- **Secrets committed to Git.** Passwords, private keys and certificates stay out of the repo (`.env` and `certs/` in `.gitignore`, with `.env.example` committed). This happened before with a MySQL password; it must not happen again.
- **Claims bigger than the work.** The README and CV describe only what is built and working.
- **Scope creep that pushes the presentable version past 10 Jan.**

## Constraints

- Hardware: Nate has no board now. Budget about €25–40. Parts must be ordered by about 1 Dec so they arrive before 14 Dec.
- Laptop: Fedora Linux, 11 GB RAM, Podman 5.8 installed (no Docker). Pico SDK and toolchain are installed in `~/.pico-sdk`.
- Network: Nate has no router. Pico W and laptop both join **his phone's mobile hotspot**. The hotspot must offer 2.4 GHz (on an iPhone: turn on "Maximise Compatibility"); the Pico W cannot use 5 GHz. Traffic between Pico and laptop stays local and does not use mobile data. The laptop's IP on the hotspot can change between sessions, and there is no router admin, so no DHCP reservation.
- Time: courses run until 13 Dec. Nate says time is not a limit (20 Nov); his time goes mainly into reviewing and understanding. Christmas falls in week 2.
- Language skills: Nate knows MicroPython (DontStress), Python, C, basic SQL from the Linux Servers and Databases course.

## Approaches considered

| Approach | Trade-off | Decision |
|---|---|---|
| A. Pico W + self-hosted server on laptop (this design) | Covers IoT, networking, Linux, SQL, security, CI. Costs €25–40 for parts. Most moving parts. | **Chosen** |
| A-cloud. Same, but with AWS IoT Core | AWS appears in ads, but Nate takes AWS in third year and does not want it now | Rejected by Nate |
| B. Virtual network/security lab (OPNsense, VLANs, Wazuh) | Free, but common among students, mostly configuration, weak demo; cybersecurity trainee ads barely name these tools | Rejected |
| C. Python network scanner tool | Free and real code, but narrow, no IoT, compared to nmap | Rejected |

## Decisions already made

- Approach A, self-hosted, no cloud (Nate).
- Hardware spend of about €25–40 is OK (Nate).
- Ready by 10 Jan for January–February applications (agreed from ad research).
- Network is Nate's phone hotspot; no router purchase (Nate).
- The assistant builds most of the code; Nate reviews and must understand it (Nate).

## Assistant's calls (Nate can change these)

- **Device language: MicroPython**, not C. Nate already knows it from DontStress, and MQTT over TLS in C on the Pico (lwIP + mbedTLS) would likely blow the time budget. C stays a possible later upgrade.
- **Sensor: BME280** on I2C (temperature, humidity, pressure). Cheap, common, well documented, gives three interesting graphs.
- **Containers with Podman and a compose file** (`podman compose`), because Docker is not installed and Podman ships with Fedora. The compose file should also work with Docker.
- **PostgreSQL** for storage, because SQL appears in the ads and in his current course.
- **Grafana** for the dashboard, provisioned from files in the repo (datasource and dashboard JSON), so a fresh clone shows the dashboard without clicking.
- **Own small certificate authority made with OpenSSL** for the TLS certificates, with a script in the repo that generates them. Certificates are not committed.
- **Mosquitto access control:** anonymous access off; each device has its own username/password; the ACL lets a device publish only to `sensors/<device_id>/readings`; the ingest service may only subscribe.
- **Ports:** only MQTT TLS (8883) is reachable from the network. PostgreSQL and Grafana are bound to localhost. Firewall rules (firewalld) are documented in the README.
- **Message format** (JSON):
  `{"device_id": "pico-01", "ts": "2026-12-20T14:05:00Z", "temperature_c": 21.4, "humidity_pct": 38.2, "pressure_hpa": 1012.6}`
  The Pico gets real time from NTP at boot.
- **Database:** one `readings` table (id, device_id, ts, temperature_c, humidity_pct, pressure_hpa, received_at) with an index on (device_id, ts).
- **Validation in the ingest service:** reject missing fields, wrong types, and values outside physical sensor ranges; log the reason.
- **Tests:** pytest unit tests for message parsing and validation, plus one integration test that runs against a PostgreSQL service container in GitHub Actions. Linter: ruff.
- **Offline buffer on the Pico:** a fixed-size in-memory buffer (for example the last 100 readings). Oldest readings are dropped when full. Not saved to flash.
- **Simulated device** (`simulator/`): a small Python script that publishes fake readings with the same TLS, credentials and message format as the Pico. It lets anyone without hardware run the whole system, lets server work start before the parts arrive, and drives one end-to-end test in GitHub Actions (simulator → broker → ingest → PostgreSQL).
- **Finding the broker on the hotspot:** the Pico connects to the laptop's IP set in its config file (`firmware/config.py`, not committed; `config.example.py` is), and verifies the TLS certificate against a fixed hostname (for example `iot-monitor.local`) passed as the server hostname, so the certificate stays valid when the IP changes. The README explains how to update the IP. mDNS can be tried as an improvement but is not required.
- **Repo name:** `secure-iot-monitor`, public under `github.com/nathansgirma`, MIT licence.
- **Repo layout:**
  ```
  firmware/        MicroPython code for the Pico W
  ingest/          Python ingest service + tests
  broker/          Mosquitto config and ACL
  grafana/         provisioning files and dashboard JSON
  db/              SQL schema
  simulator/       fake device for testing without hardware
  scripts/         certificate generation, device user creation
  docs/            diagram, screenshots, demo
  compose.yaml
  .env.example
  README.md
  SECURITY.md      what is protected, how, and known limits
  ```

## Shopping list (estimate, to verify at order time)

- Raspberry Pi Pico WH (Pico W with soldered headers): about €8–10
- BME280 breakout board (I2C, 3.3 V): about €5–12
- Small breadboard + jumper wires: about €5–8
- Micro-USB data cable (if he does not have one): about €3–5

Total about €21–35. Buy from a Finnish shop for fast delivery; check that the Pico is the **W** (Wi-Fi) model and the BME280 is not a BMP280 (BMP280 has no humidity).

## Timeline

| When | Milestone |
|---|---|
| By 1 Dec | Order parts. Create the empty public repo with README stub and `.gitignore`. |
| 1–13 Dec (optional, light) | Server stack in Podman with the simulator: Mosquitto, ingest, PostgreSQL, Grafana working without hardware. |
| 14–20 Dec | Pico reads the BME280, joins Wi-Fi, gets NTP time, publishes plain MQTT to Mosquitto running in Podman. |
| 21–27 Dec (Christmas) | Ingest service writes to PostgreSQL; Grafana dashboard shows live data. End-to-end works without security. |
| 28 Dec – 3 Jan | Security: TLS with own CA, per-device passwords, ACL, localhost-only DB/Grafana, firewall rules, secrets out of Git. Offline buffer on the Pico. |
| 4 – 10 Jan | Tests and GitHub Actions; README with diagram, screenshots and demo video; SECURITY.md; add the project to the CV. **Presentable.** |
| 11 – 17 Jan | Buffer for slips. Stretch only if done: Grafana alert when a value crosses a threshold. |

If a week slips, cut the offline buffer and stretch goals first; never cut security, tests or the README.

## Demo video (record by 10 Jan)

30–60 seconds: the board on the desk, breathing on the sensor to change humidity, the Grafana graph reacting live, then unplugging Wi-Fi and showing buffered readings arriving after reconnect.

## Left to the builder

- Exact library choices inside MicroPython (BME280 driver, MQTT client with TLS support) and the MicroPython version, as long as the server certificate is verified.
- Python ingest service structure and MQTT/PostgreSQL client libraries.
- Grafana panel design.
- Exact wording of README and SECURITY.md (Nate's voice, honest, plain English).
