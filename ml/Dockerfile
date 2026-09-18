FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ml/requirements.txt .
RUN pip install --no-cache-dir uv --upgrade pip && \
    uv pip install --system --no-cache -r requirements.txt

# Copy both ML and Monitoring folders 
COPY ml/ ./ml/
COPY monitoring/ ./monitoring/

EXPOSE 8000

# Set WORKDIR to ml so paths in main.py resolve correctly
WORKDIR /app/ml

# Boot sequence: a fresh container has no production_model.pkl (it is git/docker-ignored),
# so it waits for the DuckDB marts and the MLflow server, trains once (logging + registering
# the champion in MLflow), then serves. A restarted container keeps its model and skips training.
CMD ["bash", "-c", "if [ ! -f models/production_model.pkl ]; then echo 'No production model yet. Waiting for Dagster to build the database...'; while ! python -c \"import duckdb; duckdb.connect('/app/dataops/data/duckdb/autoimmune.duckdb', read_only=True).execute('SELECT 1 FROM main_marts.ml_patients_dataset')\" 2>/dev/null; do sleep 5; done; if [ -n \"$MLFLOW_TRACKING_URI\" ]; then echo \"Waiting for MLflow at $MLFLOW_TRACKING_URI...\"; while ! python -c \"import urllib.request; urllib.request.urlopen('$MLFLOW_TRACKING_URI/health')\" 2>/dev/null; do sleep 3; done; fi; echo 'Starting training pipeline...'; python train_pipeline.py; fi && uvicorn main:app --host 0.0.0.0 --port 8000"]
