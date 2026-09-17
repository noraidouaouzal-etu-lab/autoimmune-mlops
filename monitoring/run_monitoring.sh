#!/bin/bash
set -e

echo "Waiting for ML Backend to be ready..."
until curl -s http://ml-backend:8000/health | grep -q "healthy"; do
  sleep 5
done

echo "Starting API Health Monitor in the background..."
python monitoring/health_monitor.py --url http://ml-backend:8000 --interval 15 &

echo "Building Drift Reference from DuckDB..."
python monitoring/drift_detector.py --build-reference --data /app/dataops/duckdb/autoimmune.duckdb

echo "Starting continuous metrics and drift evaluation loop..."
while true; do
    python monitoring/drift_detector.py --check
    python monitoring/metrics.py
    sleep 60
done