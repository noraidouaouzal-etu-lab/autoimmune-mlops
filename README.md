![CI Pipeline](https://github.com/noraidouaouzal-etu-lab/autoimmune-mlops/actions/workflows/ci.yml/badge.svg)
![Docker Build](https://github.com/noraidouaouzal-etu-lab/autoimmune-mlops/actions/workflows/docker-build.yml/badge.svg)
# Autoimmune Disease Prediction — MLOps Pipeline

MLOps project integrating the team's deliverables into the single architecture
from the project brief:

```
Dataset -> dlt -> DuckDB -> dbt -> Data Quality Tests -> ML Model -> MLflow
        -> FastAPI -> Docker -> GitHub Actions -> Monitoring
```

## MLflow tracking & model registry

`ml/train_pipeline.py` logs every training execution to MLflow:

- one parent run (`train_pipeline`) with dataset sizes, the 23 selected
  features, the scaler / encoder / metadata artifacts and the champion metrics;
- one nested run per candidate (`RandomForestClassifier`, `SVC`) with its
  hyperparameters, test metrics and composite score
  (mean of balanced accuracy and weighted F1);
- the champion is logged with a signature and registered as
  `autoimmune-classifier`, alias `champion`.

Where it writes is controlled by env vars:

| Variable | Default | Notes |
|----------|---------|-------|
| `MLFLOW_TRACKING_URI` | `sqlite:///ml/mlflow.db` (artifacts in `ml/mlruns/`) | Docker Compose sets `http://mlflow:5000`. |
| `MLFLOW_EXPERIMENT_NAME` | `autoimmune-classification` | |
| `MLFLOW_MODEL_NAME` | `autoimmune-classifier` | Registered model name. |

Local run and UI:

```bash
cd ml && python train_pipeline.py && cd ..
mlflow ui --backend-store-uri sqlite:///ml/mlflow.db --port 5000   # http://localhost:5000
```

In Docker, the `mlflow` service (port 5000, data in the `mlflow_volume`
volume) starts with the stack; the backend container trains once on first
boot, logs to that server, then serves the resulting `production_model.pkl`.

## Repository layout

| Path | Owner | What's here |
|------|-------|-------------|
| `data/` | Member 3 | Raw source CSV + `CleanedDataset.csv` (notebook output). |
| `dlt_pipeline/` | Member 3 | `ingestion.py` loads the CSV into DuckDB; `run_pipeline.py`, `check_db.py`. |
| `duckdb/` | Member 3 | `autoimmune_pipeline.duckdb` — the dlt landing database. |
| `dbt/` | Members 4 + 5 | staging -> intermediate -> marts models, plus the data-quality singular tests and the **contract-enforced** `ml_patients_dataset`. |
| `ml/` | Member 1 | training notebooks (`notebooks/`) and the trained artifacts (`models/`, `scalers/`, `encoder/`, `features/`). |
| `api/` | Member 2 | FastAPI app (`main.py`) with `POST /predict`, `GET /health`, `/features`, `/metrics`. |
| `monitoring/` | Member 7 | logging, middleware, health monitor, drift detector, dashboard. |
| `docker/`, `docker-compose.yml` | Member 2 | API image. |
| `tests/` | — | API smoke tests. |
| `docs/` | Member 5 | data-quality & lineage doc + generated dbt docs site. |

## Status

| Member | Role | In this repo? |
|--------|------|---------------|
| 1 | MLOps — modeling + MLflow | Done|
| 2 | Deployment — FastAPI + Docker | Done |
| 3 | Data Engineer — dlt + DuckDB | Done |
| 4 | Data Transformation — dbt | Done |
| 5 | Data Quality — tests + contracts + lineage | Done |
| 6 | DevOps — GitHub Actions CI/CD | Done |
| 7 | Monitoring | Done |
| 8 | Product Owner — docs, backlog, report, slides | Pending |

## How the pieces connect

1. **Ingestion (dlt).** `dlt_pipeline/ingestion.py` reads
   `data/Complete_Updated_Autoimmune_Disorder_Dataset2.csv` and writes the
   `raw_medical_data.patients` table into `duckdb/autoimmune_pipeline.duckdb`.
2. **Transformation (dbt).** `dbt/` reads that DuckDB table through
   `stg_patients -> int_patients_cleaned -> patients_features ->
   ml_patients_dataset`. The final mart is the dbt equivalent of
   `data/CleanedDataset.csv`.
3. **Data quality (dbt tests).** Generic tests (`not_null`,
   `accepted_values`) live in the model YAMLs; four singular tests in
   `dbt/tests/` guard row-count preservation, the duplicate-rate band,
   unmapped diagnosis labels, and `patient_id` cardinality drift. The
   `ml_patients_dataset` model has `contract.enforced: true` — the build
   fails if a column is renamed/retyped/dropped, protecting the API and
   monitoring schema downstream.
4. **ML.** `ml/notebooks/MLTraining.ipynb` trains the RFE Random-Forest and
   produces the artifacts in `ml/models`, `ml/scalers`, `ml/encoder`,
   `ml/features`.
5. **Serving (FastAPI).** `api/main.py` loads those artifacts (paths resolved
   relative to the file) and serves predictions.
6. **Monitoring.** Every request passes through `MonitoringMiddleware`; every
   prediction is logged for the drift detector and dashboard; the health
   monitor polls `/health`.

## Quick start (local, no Docker)

```bash
pip install -r requirements.txt

# 1. ingest
python dlt_pipeline/ingestion.py

# 2. transform + data-quality gate
cd dbt && DBT_PROFILES_DIR=. dbt build && cd ..

# 3. serve  (from the repo root)
uvicorn api.main:app --host 0.0.0.0 --port 8000

# 4. monitor (separate terminal)
python monitoring/health_monitor.py
```

> **Important:** launch the API with `uvicorn api.main:app` **from the repo
> root**. Artifact paths in `api/main.py` are resolved relative to the file, so
> the working directory no longer matters — but the `api.main` module path
> needs the repo root on `PYTHONPATH`, which is the default when you run from
> root.

`bash run_pipeline.sh` runs the ingest + dbt steps and prints the serve/monitor
commands.

## Quick start (Docker)

```bash
docker compose up --build
# API -> http://localhost:8000/health
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/predict` | 23 lab/clinical features -> diagnosis label. |
| GET | `/health` | Liveness + model-loaded flag + feature count. |
| GET | `/features` | The ordered RFE feature list. |
| GET | `/metrics` | Monitoring metrics (latency, throughput, errors). |
