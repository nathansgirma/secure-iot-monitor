#!/usr/bin/env bash
# Add (or reset) an MQTT user with a random password and print the password once.
# Usage: scripts/add_device.sh <device_id>
set -euo pipefail
cd "$(dirname "$0")/.."
user="${1:?usage: add_device.sh <device_id>}"
if [[ ! "$user" =~ ^[a-z0-9-]{1,32}$ ]]; then
  echo "device id must be lowercase letters, digits and dashes (max 32)" >&2
  exit 1
fi
password="${MQTT_NEW_PASSWORD:-$(openssl rand -base64 18 | tr -d '/+=')}"
touch broker/passwd
runtime="${CONTAINER_RUNTIME:-$(command -v podman || command -v docker)}"
user_opt=()
# Docker runs containers as root; keep the file owned by us. (Rootless Podman already does.)
[[ "$(basename "$runtime")" == docker ]] && user_opt=(--user "$(id -u):$(id -g)")
"$runtime" run --rm "${user_opt[@]}" -v "$PWD/broker:/work:z" docker.io/library/eclipse-mosquitto:2 \
  mosquitto_passwd -b /work/passwd "$user" "$password"
chmod 644 broker/passwd
echo "$user password: $password"
