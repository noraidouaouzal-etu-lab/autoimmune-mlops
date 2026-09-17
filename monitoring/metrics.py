
import json
import os
from collections import Counter
from datetime import datetime, timezone

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(_THIS_DIR, "logs")
REPORTS_DIR = os.path.join(_THIS_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

PREDICTION_LOG_FILE = os.path.join(LOG_DIR, "predictions.log")
DRIFT_REPORT_FILE = os.path.join(REPORTS_DIR, "drift_report.json")
DASHBOARD_DATA_FILE = os.path.join(REPORTS_DIR, "dashboard_data.json")

from monitoring.health_monitor import compute_uptime  # noqa: E402


def _read_predictions() -> list[dict]:
    if not os.path.exists(PREDICTION_LOG_FILE):
        return []
    events = []
    with open(PREDICTION_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 2)


def build_dashboard_data() -> dict:
    events = _read_predictions()
    total = len(events)
    errors = sum(1 for e in events if e.get("status") != "success")
    latencies = [e["latency_ms"] for e in events if isinstance(e.get("latency_ms"), (int, float))]
    class_counts = Counter(
        e.get("prediction") for e in events
        if e.get("status") == "success" and e.get("prediction")
    )

    # Latency trend: last 50 predictions (for a sparkline)
    latency_trend = latencies[-50:]

    drift = None
    if os.path.exists(DRIFT_REPORT_FILE):
        with open(DRIFT_REPORT_FILE, "r", encoding="utf-8") as f:
            drift = json.load(f)

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_metrics": {
            "total_predictions": total,
            "errors": errors,
            "error_rate_pct": round(100 * errors / total, 2) if total else 0.0,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            "p50_latency_ms": _percentile(latencies, 0.50),
            "p95_latency_ms": _percentile(latencies, 0.95),
            "p99_latency_ms": _percentile(latencies, 0.99),
            "latency_trend": latency_trend,
        },
        "model_metrics": {
            "class_distribution": dict(class_counts),
        },
        "health": compute_uptime(),
        "drift": {
            "overall_status": drift.get("overall_status") if drift else "NOT_RUN",
            "drifted_features": drift.get("summary", {}).get("drifted", []) if drift else [],
            "watch_features": drift.get("summary", {}).get("watch", []) if drift else [],
            "n_samples": drift.get("n_production_samples", 0) if drift else 0,
            "features": drift.get("features", {}) if drift else {},
        },
    }

    with open(DASHBOARD_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


if __name__ == "__main__":
    d = build_dashboard_data()
    print(json.dumps(d["api_metrics"], indent=2))
    print("Health:", d["health"])
    print("Drift:", d["drift"]["overall_status"])
