"""
FastAPI serving app — Autoimmune Disease Prediction (Member 2: Deployment).

Integration notes
------------------
* Artifacts live in ../ml/{models,scalers,encoder,features} in the unified
  autoimmune-mlops/ layout. Paths are resolved relative to THIS file, so the
  app can be launched from anywhere (uvicorn api.main:app from repo root, or
  python -m uvicorn main:app from inside api/).
* The model, scaler, encoder and RFE feature list are loaded from ml/ via
  joblib.
* Monitoring (Member 7): request middleware, /metrics, /health, and
  per-prediction logging are wired in.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import joblib
import pandas as pd
import json
import time
import sys
import os

# --- Resolve paths relative to the repo, not the CWD -----------------------
API_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(API_DIR, ".."))
ML_DIR = os.path.join(ROOT_DIR, "ml")

# Make the repo root importable so the `monitoring` package is found.
sys.path.insert(0, ROOT_DIR)
from monitoring.middleware import MonitoringMiddleware, metrics_endpoint
from monitoring.logging_config import get_logger, log_prediction

app = FastAPI(title="Autoimmune Disease Prediction API", version="1.0.0")
logger = get_logger("api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Monitoring (Member 7): request logging + /metrics endpoint ---
app.add_middleware(MonitoringMiddleware)
app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])


class PatientData(BaseModel):
    ESR: float
    RBC_Count: float
    PLT_Count: float
    Hemoglobin: float
    MCH: float
    Sickness_Duration_Months: float
    Reticulocyte_Count: float
    Monocytes: float
    WBC_Count: float
    MPV: float
    MBL_Level: float
    MCV: float
    RDW: float
    C3: float
    Hematocrit: float
    Lymphocytes: float
    MCHC: float
    Neutrophils: float
    Basophils: float
    Eosinophils: float
    Age: float
    C4: float
    Esbach: float


# ---------------------------------------------------------------------------
# Artifact / model loading
# ---------------------------------------------------------------------------
try:
    model = joblib.load(os.path.join(ML_DIR, "models", "rfe_rf_model.pkl"))
    scaler = joblib.load(os.path.join(ML_DIR, "scalers", "rfe_features_scaler.pkl"))
    with open(os.path.join(ML_DIR, "encoder", "diagnosis.json"), "r") as f:
        label_mapping = json.load(f)
    feature_names = joblib.load(os.path.join(ML_DIR, "features", "rfecv_features.pkl"))
except Exception as e:
    raise RuntimeError(f"Erreur lors du chargement des artefacts: {str(e)}")


@app.on_event("startup")
async def _startup():
    logger.info("service started")


@app.post("/predict")
async def predict(patient: PatientData, request: Request):
    start = time.perf_counter()
    try:
        input_features = [
            patient.MPV, patient.Lymphocytes, patient.Esbach, patient.MBL_Level,
            patient.Basophils, patient.WBC_Count, patient.Age,
            patient.Sickness_Duration_Months, patient.Hemoglobin,
            patient.Eosinophils, patient.C4, patient.Reticulocyte_Count,
            patient.Neutrophils, patient.PLT_Count, patient.RBC_Count,
            patient.Monocytes, patient.C3, patient.Hematocrit, patient.MCV,
            patient.MCHC, patient.RDW, patient.ESR, patient.MCH,
        ]
        input_df = pd.DataFrame([input_features], columns=feature_names)
        input_scaled = scaler.transform(input_df)
        prediction = model.predict(input_scaled)
        diagnosis = label_mapping[str(prediction[0])]

        log_prediction(
            features=patient.model_dump(),
            prediction=diagnosis,
            latency_ms=(time.perf_counter() - start) * 1000,
            status="success",
            request_id=getattr(request.state, "request_id", None),
        )
        return {"diagnosis": diagnosis, "status": "success"}

    except Exception as e:
        log_prediction(
            features=patient.model_dump(),
            prediction=None,
            latency_ms=(time.perf_counter() - start) * 1000,
            status="error",
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/features")
async def get_features():
    # feature_names is a numpy array on disk; list() makes it JSON-serializable
    return {"features": list(feature_names)}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "n_features": len(feature_names),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
