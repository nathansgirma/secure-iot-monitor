# Security

This file explains what the system protects, how, and what it does not protect. It's a learning project running on one laptop, not a production system, but the security is real and tested.

## What is protected and how

| Threat | Protection | Where |
|---|---|---|
| Someone on the same Wi-Fi reads or changes sensor data in transit | MQTT only over TLS 1.2+ on port 8883. Plain MQTT (1883) is not enabled. Clients check the server certificate against our own CA. | `broker/mosquitto.conf`, `scripts/gen_certs.sh` |
| A stranger connects to the broker | Anonymous access is off. Every client has its own username and password (stored hashed by Mosquitto). | `broker/mosquitto.conf`, `scripts/add_device.sh` |
| One device pretends to be another | The access list lets a device write only to `sensors/<its own username>/readings`. The ingest service also rejects messages whose `device_id` doesn't match the topic. | `broker/acl`, `ingest/ingest/messages.py` |
| One client kicks another off the broker | `use_username_as_clientid` makes every client's ID equal its username, so a device can't reuse another client's ID to disconnect it. | `broker/mosquitto.conf` |
| The ingest login is stolen | The ingest user may read all readings. The ACL's device rule would let it write to `sensors/ingest/readings`, but the ingest service rejects any reading whose `device_id` is `ingest`. Someone with this password could still disconnect the real ingest service by logging in as it, so treat it like a server password. | `broker/acl`, `ingest/ingest/messages.py` |
| Bad or malicious data | The broker refuses packets over 2 KB. Every message is checked: UTF-8 JSON object, all fields present, numbers really numbers, device id format, timestamp a real date between 2024 and 5 minutes ahead, and values within the BME280's physical range. Bad messages are logged and dropped, and any unexpected error while handling a message is logged instead of stopping the service (tests cover broken JSON, deep nesting, huge numbers and impossible dates). | `ingest/ingest/messages.py`, `ingest/ingest/main.py` |
| Database attacked over the network | PostgreSQL has no published port. Only containers on the internal network can reach it. | `compose.yaml` |
| Dashboard reached from other machines | Grafana listens on `127.0.0.1:3000` only. Sign-up and anonymous access are off. | `compose.yaml` |
| Grafana used to change data | Grafana logs in to the database as `grafana`, which can only `SELECT` from `readings`. | `db/02-grafana-role.sh` |
| Secrets leaked through Git | Passwords, keys and certificates are generated locally (`scripts/setup.sh`) and are in `.gitignore`: `.env`, `certs/`, `broker/passwd`, `firmware/config.py`. Only examples are committed. | `.gitignore` |
| Containers running as root | The ingest container runs as a non-root user. | `ingest/Containerfile` |

Checks that were done by hand while building (see the commit history and CI):

- connecting without a login, or with a wrong password → refused
- connecting without TLS on 1883 → refused
- `pico-sim` publishing to `sensors/pico-01/readings` → dropped, nothing stored
- from the network, only port 8883 is open; 3000 is on localhost only; 5432 is not published
- the `grafana` database user trying `DELETE` → permission denied
- a message with an impossible date (30 February), broken JSON or a huge number → rejected, service keeps running
- a device connecting with the client ID `ingest` → the ingest service stays connected

## Firewall

On Fedora, open only the MQTT port:

```bash
sudo firewall-cmd --add-port=8883/tcp
sudo firewall-cmd --add-port=8883/tcp --permanent
```

## Known limits

- **Self-made CA.** The certificates come from a CA created by `scripts/gen_certs.sh`. That's fine for a private system, but anyone with `certs/ca.key` can create trusted certificates, so keep it private. It's valid for 825 days.
- **Passwords, not client certificates.** Devices log in with a username and password inside TLS. Client certificates (mutual TLS) would be stronger.
- **The device stores its password in plain text** in `config.py` on the Pico. Someone with physical access to the board can read it. If a board is lost, reset its password with `scripts/add_device.sh <device-id>`.
- **Readings can be lost in some cases:**
  - The Pico's buffer is in RAM: up to 100 readings, lost on power loss.
  - Broker persistence is off. If the broker itself restarts, readings it was holding for the ingest service are lost.
  - If the database restarts or goes down, readings that arrive while it's unreachable are dropped rather than retried, and the service can be slow to catch up while it waits for the database.
- **The laptop is the server.** When it sleeps, the devices buffer until it's back (up to 100 readings, about 16 minutes).
- **Grafana admin password** is random and stored in `.env`. Change it if `.env` was ever shared.
