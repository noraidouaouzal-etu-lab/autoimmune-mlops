Excellent, tout est vert ✅ ! Les 3 runs (CI Pipeline sur main, Docker Build sur main, CI Pipeline sur dev) ont tous réussi. Ça veut dire :

Le linting (flake8/black/isort) est passé
Les tests pytest (test_api.py + test_monitoring.py) sont passés — donc le modèle a bien chargé et le endpoint /predict fonctionne
L'image Docker s'est bien construite et a été poussée sur ghcr.io

Ta partie CI/CD est fonctionnelle. 🎉
Ce qu'il te reste à faire pour finaliser ton rôle de Member 6 :

Ajoute un badge de statut au README pour montrer visuellement que le CI fonctionne (bon pour ton rapport/présentation) :

markdown![CI Pipeline](https://github.com/noraidouaouzal-etu-lab/autoimmune-mlops/actions/workflows/ci.yml/badge.svg)
![Docker Build](https://github.com/noraidouaouzal-etu-lab/autoimmune-mlops/actions/workflows/docker-build.yml/badge.svg)

Ajoute tes collègues comme collaborateurs (Settings → Collaborators) si pas encore fait, pour qu'ils puissent pusher chacun sur leur module.
Protège la branche main (Settings → Branches → Add branch protection rule) : exige que le CI passe avant de merger une pull request. C'est une bonne pratique DevOps à mentionner dans ton rapport.
Retire les continue-on-error: true du ci.yml une fois que tu es sûre que le code de toute l'équipe respecte le style — comme ça le lint bloquera vraiment les erreurs au lieu de juste les signaler.

Tu veux que je t'aide avec l'un de ces points, ou avec la doc/rapport à rendre sur ta partie CI/CD ?
# Autoimmune Disease Prediction — MLOps Pipeline

MLOps project integrating the team's deliverables into the single architecture
from the project brief:

```
Dataset -> dlt -> DuckDB -> dbt -> Data Quality Tests -> ML Model -> [MLflow]
        -> FastAPI -> Docker -> [GitHub Actions] -> Monitoring
```

Stages in `[brackets]` (MLflow tracking/registry, GitHub Actions CI) are owned
by Members 1 and 6 and are **not yet included** — see "Status" below.

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
| 1 | MLOps — modeling + MLflow | Modeling done (notebooks + artifacts in `ml/`). MLflow tracking/registry pending. |
| 2 | Deployment — FastAPI + Docker | Done |
| 3 | Data Engineer — dlt + DuckDB | Done |
| 4 | Data Transformation — dbt | Done |
| 5 | Data Quality — tests + contracts + lineage | Done |
| 6 | DevOps — GitHub Actions CI/CD | Pending |
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
