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

# CHANGED: Checks for both models, and uses the robust table-check wait loop
CMD ["bash", "-c", "if [ ! -f models/rfe_rf_model.pkl ] && [ ! -f models/production_model.pkl ]; then echo 'Models not found! Waiting for Dagster to build the database...'; while ! python -c \"import duckdb; duckdb.connect('/app/dataops/data/duckdb/autoimmune.duckdb', read_only=True).execute('SELECT 1 FROM main_marts.ml_patients_dataset')\" 2>/dev/null; do sleep 5; done; echo 'Database found! Starting training pipeline...'; python train_pipeline.py; fi && uvicorn main:app --host 0.0.0.0 --port 8000"]
