#!/bin/bash
set -e

# CHANGED: Updated hostname to match the production service name
echo "Waiting for ML Backend to be ready..."
until curl -s http://backend:8000/health | grep -q "healthy"; do
  sleep 5
done

echo "Starting API Health Monitor in the background..."
python monitoring/health_monitor.py --url http://backend:8000 --interval 15 &

DB_PATH="/app/dataops/data/duckdb/autoimmune.duckdb"

echo "Waiting for Dagster to materialize the DuckDB database..."
while [ ! -f "$DB_PATH" ]; do
  echo "Database not found yet. Please run the Dagster pipeline. Waiting 30s..."
  sleep 30
done

echo "Building Drift Reference from DuckDB..."
python monitoring/drift_detector.py --build-reference --data "$DB_PATH"

echo "Starting continuous metrics and drift evaluation loop..."
while true; do
    python monitoring/drift_detector.py --check
    python monitoring/metrics.py
    sleep 60
done