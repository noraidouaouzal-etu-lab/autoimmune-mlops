import argparse
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

try:
    from scipy.stats import ks_2samp
    _HAS_SCIPY = True
except Exception:  # scipy optional; PSI still works without it
    _HAS_SCIPY = False

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(_THIS_DIR, "reports")
LOG_DIR = os.path.join(_THIS_DIR, "logs")
os.makedirs(REPORTS_DIR, exist_ok=True)

REFERENCE_FILE = os.path.join(REPORTS_DIR, "reference_stats.json")
PREDICTION_LOG_FILE = os.path.join(LOG_DIR, "predictions.log")
DRIFT_REPORT_FILE = os.path.join(REPORTS_DIR, "drift_report.json")

# The 23 model input features (must match features/rfecv_features.pkl)
MONITORED_FEATURES = [
    "Age", "Sickness_Duration_Months", "RBC_Count", "Hemoglobin", "Hematocrit",
    "MCV", "MCH", "MCHC", "RDW", "Reticulocyte_Count", "WBC_Count", "Neutrophils",
    "Lymphocytes", "Monocytes", "Eosinophils", "Basophils", "PLT_Count", "MPV",
    "Esbach", "MBL_Level", "ESR", "C3", "C4",
]

PSI_WATCH = 0.10
PSI_ALERT = 0.25
KS_ALPHA = 0.05
N_BINS = 10


# ---------------------------------------------------------------------------
# Reference building
# ---------------------------------------------------------------------------
def build_reference(data_path: str) -> dict:
    """Compute reference bin edges + stats from the training dataset."""
    df = pd.read_csv(data_path)
    reference = {"created_at": datetime.now(timezone.utc).isoformat(), "features": {}}

    for feat in MONITORED_FEATURES:
        if feat not in df.columns:
            continue
        series = pd.to_numeric(df[feat], errors="coerce").dropna()
        if series.empty:
            continue
        # Quantile-based bin edges make PSI robust to skewed clinical values.
        quantiles = np.linspace(0, 1, N_BINS + 1)
        edges = np.unique(np.quantile(series, quantiles))
        if len(edges) < 3:  # near-constant feature: fall back to min/max span
            edges = np.linspace(series.min(), series.max() + 1e-9, 3)
        counts, _ = np.histogram(series, bins=edges)
        proportions = counts / counts.sum()

        reference["features"][feat] = {
            "edges": edges.tolist(),
            "proportions": proportions.tolist(),
            "mean": float(series.mean()),
            "std": float(series.std()),
            "sample": series.sample(min(2000, len(series)), random_state=42).tolist(),
        }

    # Reference label distribution, if present.
    if "Diagnosis" in df.columns:
        vc = df["Diagnosis"].value_counts(normalize=True).sort_index()
        reference["label_distribution"] = {str(k): float(v) for k, v in vc.items()}

    with open(REFERENCE_FILE, "w", encoding="utf-8") as f:
        json.dump(reference, f, indent=2)
    return reference


def load_reference() -> dict:
    if not os.path.exists(REFERENCE_FILE):
        raise FileNotFoundError(
            "Reference not built yet. Run with --build-reference first."
        )
    with open(REFERENCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Production data loading
# ---------------------------------------------------------------------------
def load_production_features(last_n: int | None = None) -> pd.DataFrame:
    """Read logged prediction events into a feature DataFrame."""
    if not os.path.exists(PREDICTION_LOG_FILE):
        return pd.DataFrame()
    rows = []
    with open(PREDICTION_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            feats = obj.get("features")
            if isinstance(feats, dict):
                record = dict(feats)
                record["_prediction"] = obj.get("prediction")
                rows.append(record)
    df = pd.DataFrame(rows)
    if last_n and not df.empty:
        df = df.tail(last_n)
    return df


# ---------------------------------------------------------------------------
# PSI
# ---------------------------------------------------------------------------
def _psi(ref_props: list[float], cur_values: np.ndarray, edges: list[float]) -> float:
    edges = np.array(edges)
    counts, _ = np.histogram(cur_values, bins=edges)
    cur_props = counts / counts.sum() if counts.sum() > 0 else np.zeros_like(counts, dtype=float)
    ref = np.array(ref_props)
    eps = 1e-6
    ref = np.clip(ref, eps, None)
    cur = np.clip(cur_props, eps, None)
    return float(np.sum((cur - ref) * np.log(cur / ref)))


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------
def check_drift(last_n: int | None = None) -> dict:
    reference = load_reference()
    prod = load_production_features(last_n=last_n)

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "n_production_samples": int(len(prod)),
        "features": {},
        "summary": {"drifted": [], "watch": [], "stable": []},
    }

    if prod.empty:
        report["note"] = "No production predictions logged yet."
        _save_report(report)
        return report

    for feat, ref_stats in reference["features"].items():
        if feat not in prod.columns:
            continue
        cur = pd.to_numeric(prod[feat], errors="coerce").dropna().values
        if len(cur) == 0:
            continue

        psi_val = _psi(ref_stats["proportions"], cur, ref_stats["edges"])

        ks_p = None
        if _HAS_SCIPY and ref_stats.get("sample"):
            try:
                _, ks_p = ks_2samp(ref_stats["sample"], cur)
            except Exception:
                ks_p = None

        if psi_val > PSI_ALERT or (ks_p is not None and ks_p < KS_ALPHA and psi_val > PSI_WATCH):
            status = "DRIFT"
            report["summary"]["drifted"].append(feat)
        elif psi_val > PSI_WATCH:
            status = "WATCH"
            report["summary"]["watch"].append(feat)
        else:
            status = "STABLE"
            report["summary"]["stable"].append(feat)

        report["features"][feat] = {
            "psi": round(psi_val, 4),
            "ks_pvalue": round(ks_p, 4) if ks_p is not None else None,
            "status": status,
            "ref_mean": round(ref_stats["mean"], 3),
            "cur_mean": round(float(np.mean(cur)), 3),
        }

    # Prediction (label) distribution drift
    if "_prediction" in prod.columns and reference.get("label_distribution"):
        cur_labels = prod["_prediction"].dropna()
        if not cur_labels.empty:
            cur_dist = cur_labels.value_counts(normalize=True).to_dict()
            report["prediction_distribution"] = {
                "current": {str(k): round(float(v), 3) for k, v in cur_dist.items()},
            }

    report["overall_status"] = (
        "DRIFT" if report["summary"]["drifted"]
        else "WATCH" if report["summary"]["watch"]
        else "STABLE"
    )
    _save_report(report)
    return report


def _save_report(report: dict) -> None:
    with open(DRIFT_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data & prediction drift detector.")
    parser.add_argument("--build-reference", action="store_true",
                        help="Build reference distribution from training data.")
    parser.add_argument("--data", default=os.path.join(_THIS_DIR, "..", "data", "CleanedDataset.csv"),
                        help="Path to the training CSV for reference building.")
    parser.add_argument("--check", action="store_true", help="Run a drift check.")
    parser.add_argument("--last-n", type=int, default=None,
                        help="Only use the last N logged predictions.")
    args = parser.parse_args()

    if args.build_reference:
        ref = build_reference(args.data)
        print(f"Reference built for {len(ref['features'])} features -> {REFERENCE_FILE}")
    if args.check:
        rep = check_drift(last_n=args.last_n)
        print(json.dumps(rep["summary"], indent=2))
        print("Overall:", rep.get("overall_status"))
    if not args.build_reference and not args.check:
        parser.print_help()
