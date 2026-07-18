#!/usr/bin/env bash
# Creates the InfluxDB database used by the JMeter Backend Listener and
# a 30-day default retention policy, so Grafana always has up to 30 days
# of trend history available. Idempotent — safe to re-run.
#
# Usage: bash scripts/setup_influxdb.sh
# Env vars: INFLUXDB_HOST, INFLUXDB_PORT, INFLUXDB_DB, RETENTION_DAYS

set -euo pipefail

INFLUXDB_HOST="${INFLUXDB_HOST:-localhost}"
INFLUXDB_PORT="${INFLUXDB_PORT:-8086}"
INFLUXDB_DB="${INFLUXDB_DB:-jmeter}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
BASE_URL="http://${INFLUXDB_HOST}:${INFLUXDB_PORT}"

echo "Waiting for InfluxDB at ${BASE_URL} ..."
for i in $(seq 1 30); do
  if curl -sf "${BASE_URL}/ping" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
if ! curl -sf "${BASE_URL}/ping" >/dev/null 2>&1; then
  echo "InfluxDB did not become ready at ${BASE_URL}" >&2
  exit 1
fi

echo "Creating database '${INFLUXDB_DB}' (idempotent)..."
curl -sf -POST "${BASE_URL}/query" --data-urlencode "q=CREATE DATABASE \"${INFLUXDB_DB}\"" >/dev/null

echo "Creating default ${RETENTION_DAYS}-day retention policy..."
curl -sf -POST "${BASE_URL}/query" \
  --data-urlencode "q=CREATE RETENTION POLICY \"jmeter_${RETENTION_DAYS}d\" ON \"${INFLUXDB_DB}\" DURATION ${RETENTION_DAYS}d REPLICATION 1 DEFAULT" >/dev/null

echo "Done. Database=${INFLUXDB_DB}, retention=${RETENTION_DAYS}d (default)."
