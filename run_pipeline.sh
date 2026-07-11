#!/usr/bin/env bash
# Local pipeline runner (mirrors the PDF architecture).
set -e

echo "[1/4] dlt ingestion -> DuckDB"
python dlt_pipeline/ingestion.py

echo "[2/4] dbt transforms + data-quality tests"
( cd dbt && DBT_PROFILES_DIR=. dbt build )

echo "[3/4] launch API (Ctrl+C to stop)"
echo "      uvicorn api.main:app --host 0.0.0.0 --port 8000"
echo "[4/4] in another terminal: python monitoring/health_monitor.py"
