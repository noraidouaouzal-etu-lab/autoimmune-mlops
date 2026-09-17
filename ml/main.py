"""
FastAPI serving app — Autoimmune Disease Prediction Backend.
"""
import os
import sys
import json
import time
import joblib
import pandas as pd
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Path Resolution -------------------------------------------------------
ML_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(ML_DIR, ".."))

sys.path.insert(0, ROOT_DIR)
from monitoring.middleware import MonitoringMiddleware, metrics_endpoint
from monitoring.logging_config import get_logger, log_prediction

logger = get_logger("api")

# --- Global Artifact Variables ---------------------------------------------
model = None
scaler = None
label_mapping = {}
feature_names = []

# --- Lifespan Context Manager ----------------------------------------------
# Must be defined BEFORE initializing FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, scaler, label_mapping, feature_names
    logger.info("Service starting up... Loading ML artifacts.")
    try:
        # Note: You are currently hardcoding the Random Forest model. 
        # Update this path if you start using a dynamic production_model.pkl
        model_path = os.path.join(ML_DIR, "models", "rfe_rf_model.pkl")
        model = joblib.load(model_path)
        scaler = joblib.load(os.path.join(ML_DIR, "scalers", "rfe_features_scaler.pkl"))
        
        with open(os.path.join(ML_DIR, "encoder", "diagnosis.json"), "r") as f:
            label_mapping = json.load(f)
            
        feature_names = list(joblib.load(os.path.join(ML_DIR, "features", "rfecv_features.pkl")))
        logger.info("Artifacts loaded successfully!")
    except Exception as e:
        logger.error(f"Failed to load artifacts: {e}")
        raise RuntimeError(f"Startup failed: {e}")
        
    yield  # The API runs and accepts requests while paused at this line
    
    logger.info("Service shutting down cleanly. Clearing memory...")
    model = None
    scaler = None
    label_mapping.clear()
    feature_names.clear()

# --- App Initialization ----------------------------------------------------
app = FastAPI(
    title="Autoimmune Disease Prediction API", 
    version="1.0.0", 
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# --- Endpoints -------------------------------------------------------------
@app.post("/predict")
async def predict(patient: PatientData, request: Request):
    start = time.perf_counter()
    try:
        # Enforce exact feature ordering
        patient_dict = patient.model_dump()
        input_df = pd.DataFrame([patient_dict])[feature_names]
        input_scaled = scaler.transform(input_df)
        
        # Predict
        pred_idx = model.predict(input_scaled)[0]
        diagnosis = label_mapping[str(pred_idx)]
        
        # Extract confidence for the Streamlit UI
        confidence = None
        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(input_scaled)[0]
            confidence = round(float(probs[pred_idx]) * 100, 2)

        log_prediction(
            features=patient_dict,
            prediction=diagnosis,
            latency_ms=(time.perf_counter() - start) * 1000,
            status="success",
            request_id=getattr(request.state, "request_id", None),
        )
        
        return {
            "diagnosis": diagnosis, 
            "confidence": confidence, 
            "status": "success"
        }

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
    return {"features": feature_names}

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