#!/bin/sh
# Builds /mosquitto/config/passwd from env vars on every container start.
# The passwd file is ephemeral — recreated each time, never stored on disk.
set -e

PASSWD_FILE="/mosquitto/config/passwd"

# Ensure config dir exists (it always does in the official image, but be safe)
mkdir -p /mosquitto/config

# Start with a fresh (empty) passwd file
: > "$PASSWD_FILE"

# Ingestion service account
if [ -n "$MQTT_INGESTION_PASSWORD" ]; then
    mosquitto_passwd -b "$PASSWD_FILE" ingestion "$MQTT_INGESTION_PASSWORD"
    echo "[entrypoint] Added MQTT user: ingestion"
else
    echo "[entrypoint] WARNING: MQTT_INGESTION_PASSWORD not set — ingestion cannot connect via TLS"
fi

# Optional: test device account for sim_publisher TLS mode
# Set MQTT_TEST_DEVICE_UID and MQTT_TEST_DEVICE_PASSWORD in .env to use.
if [ -n "$MQTT_TEST_DEVICE_UID" ] && [ -n "$MQTT_TEST_DEVICE_PASSWORD" ]; then
    mosquitto_passwd -b "$PASSWD_FILE" "$MQTT_TEST_DEVICE_UID" "$MQTT_TEST_DEVICE_PASSWORD"
    echo "[entrypoint] Added MQTT user: $MQTT_TEST_DEVICE_UID"
fi

echo "[entrypoint] Starting mosquitto..."
exec mosquitto -c /mosquitto/config/mosquitto.conf "$@"
