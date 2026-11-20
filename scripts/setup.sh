#!/usr/bin/env bash
# One-time setup: random passwords in .env, TLS certificates, and the ingest MQTT user.
set -euo pipefail
cd "$(dirname "$0")/.."
rand() { openssl rand -base64 18 | tr -d '/+='; }

if [[ ! -f .env ]]; then
  {
    echo "MQTT_INGEST_PASSWORD=$(rand)"
    echo "POSTGRES_PASSWORD=$(rand)"
    echo "GRAFANA_ADMIN_PASSWORD=$(rand)"
  } > .env
  chmod 600 .env
  echo "Created .env with random passwords"
fi
set -a; source .env; set +a

[[ -f certs/ca.key ]] || scripts/gen_certs.sh
MQTT_NEW_PASSWORD="$MQTT_INGEST_PASSWORD" scripts/add_device.sh ingest >/dev/null
echo "Added MQTT user 'ingest'"
echo "Next: scripts/add_device.sh <device-id> for each device, then: podman compose up -d"
