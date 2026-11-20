#!/bin/bash
# Grafana gets its own database user that can only read the readings table.
set -euo pipefail
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v pw="$GRAFANA_DB_PASSWORD" <<'SQL'
CREATE ROLE grafana LOGIN PASSWORD :'pw';
GRANT CONNECT ON DATABASE iot TO grafana;
GRANT USAGE ON SCHEMA public TO grafana;
GRANT SELECT ON readings TO grafana;
SQL
