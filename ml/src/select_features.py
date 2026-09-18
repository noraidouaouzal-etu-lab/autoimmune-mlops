import os
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import RFECV

# The 23 lab/clinical features selected by RFECV in notebooks/MLTraining.ipynb.
# Used by default so the trained model, the FastAPI schema (PatientData), the
# scaler and the monitoring drift detector always agree on the same inputs.
SELECTED_FEATURES = [
    "Age", "Sickness_Duration_Months", "RBC_Count", "Hemoglobin", "Hematocrit",
    "MCV", "MCH", "MCHC", "RDW", "Reticulocyte_Count", "WBC_Count", "Neutrophils",
    "Lymphocytes", "Monocytes", "Eosinophils", "Basophils", "PLT_Count", "MPV",
    "Esbach", "MBL_Level", "ESR", "C3", "C4",
]

# Set RUN_RFECV=1 to re-run the full RFECV search instead of using the fixed list.
# Slow (RandomForest x 5-fold CV over every feature) and the selected set may
# differ from the 23 the API expects, so keep it for experiments, not for serving.
RUN_RFECV = os.getenv("RUN_RFECV", "0") == "1"


def _rfecv_search(X_train, y_train):
    """Selects optimal features using RFECV with a Random Forest estimator."""
    estimator = RandomForestClassifier(n_estimators=100, random_state=42)
    rfecv = RFECV(estimator=estimator, step=1, cv=5, scoring='accuracy')
    rfecv.fit(X_train, y_train)
    return list(X_train.columns[rfecv.support_])


def perform_rfecv(X_train, y_train, features_save_path):
    """Returns the selected feature list and saves it to features_save_path."""
    if RUN_RFECV:
        selected_features = _rfecv_search(X_train, y_train)
    else:
        missing = [f for f in SELECTED_FEATURES if f not in X_train.columns]
        if missing:
            raise ValueError(f"Training data is missing expected features: {missing}")
        selected_features = list(SELECTED_FEATURES)

    joblib.dump(selected_features, features_save_path)
    return selected_features
