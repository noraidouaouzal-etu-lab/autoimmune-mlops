import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from ml.main import app, PatientData

client = TestClient(app)


def _sample_payload():
    return {name: 1.0 for name in PatientData.model_fields}


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["model_loaded"] is True
    assert body["n_features"] == 23


def test_features_endpoint():
    r = client.get("/features")
    assert r.status_code == 200
    assert len(r.json()["features"]) == 23


def test_predict_contract():
    r = client.post("/predict", json=_sample_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert isinstance(body["diagnosis"], str)


def test_predict_rejects_missing_field():
    bad = _sample_payload()
    del bad["Age"]
    r = client.post("/predict", json=bad)
    assert r.status_code == 422
