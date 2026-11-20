#!/usr/bin/env bash
# Wait until the database holds at least N readings (default 6). Used by CI.
set -euo pipefail
want="${1:-6}"
compose="${COMPOSE:-podman compose}"
for _ in $(seq 1 60); do
  got=$($compose exec -T postgres psql -U iot -d iot -tAc "select count(*) from readings" 2>/dev/null | tr -d '[:space:]' || true)
  if [[ "${got:-0}" =~ ^[0-9]+$ ]] && (( got >= want )); then
    echo "OK: $got readings in the database"
    exit 0
  fi
  sleep 1
done
echo "FAIL: expected at least $want readings, got '${got:-none}'" >&2
$compose logs ingest mosquitto | tail -50 >&2
exit 1
