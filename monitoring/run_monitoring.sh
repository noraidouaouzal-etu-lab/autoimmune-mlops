#!/bin/bash
set -e

echo "Waiting for ML Backend to be ready..."
until curl -s http://backend:8000/health | grep -q "healthy"; do
  sleep 5
done

echo "Starting API Health Monitor in the background..."
python monitoring/health_monitor.py --url http://backend:8000 --interval 15 &

DB_PATH="/app/dataops/data/duckdb/autoimmune.duckdb"

# CHANGED: Wait until the actual mart table is queryable, not just when the file appears
echo "Waiting for Dagster to fully materialize the DuckDB database and marts..."
while ! python -c "import duckdb; duckdb.connect('$DB_PATH', read_only=True).execute('SELECT 1 FROM main_marts.ml_patients_dataset')" 2>/dev/null; do
  echo "Waiting for Dagster pipeline to finish... (Retrying in 15s)"
  sleep 15
done

echo "Building Drift Reference from DuckDB..."
python monitoring/drift_detector.py --build-reference --data "$DB_PATH"

echo "Starting continuous metrics and drift evaluation loop..."
while true; do
    python monitoring/drift_detector.py --check
    python monitoring/metrics.py
    sleep 60
done
