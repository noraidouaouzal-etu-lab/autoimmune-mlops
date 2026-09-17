"""
test_monitoring.py
Unit tests for the monitoring module.

Run:  pytest monitoring/tests/ -v
"""

import json
import os
import tempfile

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def test_log_prediction_writes_json_line():
    from monitoring import logging_config as lc

    with tempfile.TemporaryDirectory() as tmp:
        lc.PREDICTION_LOG_FILE = os.path.join(tmp, "predictions.log")
        lc._prediction_logger = None  # force re-init to new path
        lc.log_prediction(
            features={"Age": 40.0, "ESR": 20.0},
            prediction="normal",
            latency_ms=12.3,
            status="success",
        )
        with open(lc.PREDICTION_LOG_FILE) as f:
            line = f.readline().strip()
        obj = json.loads(line)
        assert obj["event"] == "prediction"
        assert obj["prediction"] == "normal"
        assert obj["status"] == "success"
        assert obj["features"]["Age"] == 40.0


# ---------------------------------------------------------------------------
# PSI math
# ---------------------------------------------------------------------------
def test_psi_zero_for_identical_distributions():
    from monitoring.drift_detector import _psi

    data = np.random.normal(50, 10, 5000)
    edges = np.quantile(data, np.linspace(0, 1, 11))
    counts, _ = np.histogram(data, bins=edges)
    props = (counts / counts.sum()).tolist()
    psi = _psi(props, data, edges.tolist())
    assert psi < 0.05  # identical data -> ~0


def test_psi_large_for_shifted_distribution():
    from monitoring.drift_detector import _psi

    ref = np.random.normal(50, 10, 5000)
    edges = np.quantile(ref, np.linspace(0, 1, 11))
    counts, _ = np.histogram(ref, bins=edges)
    props = (counts / counts.sum()).tolist()
    shifted = np.random.normal(90, 10, 5000)  # big mean shift
    psi = _psi(props, shifted, edges.tolist())
    assert psi > 0.25  # clear drift


# ---------------------------------------------------------------------------
# Health uptime
# ---------------------------------------------------------------------------
def test_compute_uptime_mixed(monkeypatch):
    from monitoring import health_monitor as hm

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "health.log")
        rows = [
            {"up": True, "response_time_ms": 10.0, "timestamp": "t1"},
            {"up": True, "response_time_ms": 12.0, "timestamp": "t2"},
            {"up": False, "response_time_ms": 5000.0, "timestamp": "t3"},
            {"up": True, "response_time_ms": 11.0, "timestamp": "t4"},
        ]
        with open(path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        monkeypatch.setattr(hm, "HEALTH_LOG_FILE", path)
        stats = hm.compute_uptime()
        assert stats["probes"] == 4
        assert stats["uptime_pct"] == 75.0
        assert stats["last_status"] == "UP"


# ---------------------------------------------------------------------------
# Health probe against a down service
# ---------------------------------------------------------------------------
def test_probe_unreachable_returns_down():
    from monitoring.health_monitor import probe_once

    result = probe_once("http://127.0.0.1:59999")  # nothing listening
    assert result["up"] is False
    assert result["status_code"] is None


# ---------------------------------------------------------------------------
# Metrics percentile helper
# ---------------------------------------------------------------------------
def test_percentile():
    from monitoring.metrics import _percentile

    vals = list(range(1, 101))  # 1..100
    assert _percentile(vals, 0.50) == pytest.approx(50.5, abs=1.0)
    assert _percentile(vals, 0.95) >= 95
    assert _percentile([], 0.95) == 0.0


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
