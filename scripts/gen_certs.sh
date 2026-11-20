#!/usr/bin/env bash
# Make a private certificate authority (CA) and a server certificate for the MQTT broker.
# Output goes to certs/ (never committed).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p certs
cd certs

if [[ -f ca.key ]]; then
  echo "certs/ already has a CA. Delete certs/ first to make new ones." >&2
  exit 1
fi

openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -keyout ca.key -out ca.crt -subj "/CN=secure-iot-monitor CA"

openssl req -newkey rsa:2048 -nodes \
  -keyout server.key -out server.csr -subj "/CN=iot-monitor.local"

cat > server.ext <<EXT
subjectAltName = DNS:iot-monitor.local, DNS:localhost
extendedKeyUsage = serverAuth
EXT

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -days 825 -out server.crt -extfile server.ext

rm -f server.csr server.ext ca.srl
chmod 600 ca.key
chmod 644 server.key   # read by the broker container user
echo "Created certs/ca.crt, certs/server.crt and certs/server.key"
