import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from ml.main import app, PatientData

# Use a fixture with a context manager to trigger the FastAPI lifespan events (loading the model)
@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def _sample_payload():
    return {name: 1.0 for name in PatientData.model_fields}

def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["model_loaded"] is True
    assert body["n_features"] == 23

def test_features_endpoint(client):
    r = client.get("/features")
    assert r.status_code == 200
    assert len(r.json()["features"]) == 23

def test_predict_contract(client):
    r = client.post("/predict", json=_sample_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert isinstance(body["diagnosis"], str)

def test_predict_rejects_missing_field(client):
    bad = _sample_payload()
    del bad["Age"]
    r = client.post("/predict", json=bad)
    assert r.status_code == 422
