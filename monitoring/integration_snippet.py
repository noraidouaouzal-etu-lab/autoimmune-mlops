"""
integration_snippet.py
=======================
Reference for the Deployment Lead (Member 2). It shows the minimal changes to wire monitoring into the FastAPI service so that
logging, /metrics, and drift data collection all work automatically.

There are exactly two hooks. Copy them into api/main.py.

--------------------------------------------------------------------------
HOOK 1 — enable request logging + /metrics (add once, near app creation)
--------------------------------------------------------------------------

    from fastapi import FastAPI
    from monitoring.middleware import MonitoringMiddleware, metrics_endpoint
    from monitoring.logging_config import get_logger

    app = FastAPI()
    logger = get_logger("api")

    app.add_middleware(MonitoringMiddleware)
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])

    @app.on_event("startup")
    async def _startup():
        logger.info("service started")

--------------------------------------------------------------------------
HOOK 2 — log each prediction's features (inside the /predict handler)
--------------------------------------------------------------------------
Add this right before you `return` the prediction result. `patient` is the
pydantic model already used in main.py; `.model_dump()` (pydantic v2) or
`.dict()` (v1) turns it into the feature dict the drift detector expects.

    import time
    from monitoring.logging_config import log_prediction

    @app.post("/predict")
    async def predict(patient: PatientData, request: Request):
        start = time.perf_counter()
        try:
            # ... existing preprocessing + model.predict(...) ...
            result = {"diagnosis": label_mapping[str(prediction[0])], "status": "success"}
            log_prediction(
                features=patient.model_dump(),      # or patient.dict() on pydantic v1
                prediction=result["diagnosis"],
                latency_ms=(time.perf_counter() - start) * 1000,
                status="success",
                request_id=getattr(request.state, "request_id", None),
            )
            return result
        except Exception as e:
            log_prediction(
                features=patient.model_dump(),
                prediction=None,
                latency_ms=(time.perf_counter() - start) * 1000,
                status="error",
                error=str(e),
            )
            raise


"""
