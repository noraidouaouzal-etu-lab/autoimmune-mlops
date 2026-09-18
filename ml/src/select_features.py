import joblib

# The 23 lab/clinical features selected by RFECV in notebooks/MLTraining.ipynb.
# Kept as a fixed list so the trained model, the FastAPI schema (PatientData),
# the scaler and the monitoring drift detector always agree on the same inputs.
# Re-run the RFECV cell in the notebook if you ever want to revisit this list.
SELECTED_FEATURES = [
    "Age", "Sickness_Duration_Months", "RBC_Count", "Hemoglobin", "Hematocrit",
    "MCV", "MCH", "MCHC", "RDW", "Reticulocyte_Count", "WBC_Count", "Neutrophils",
    "Lymphocytes", "Monocytes", "Eosinophils", "Basophils", "PLT_Count", "MPV",
    "Esbach", "MBL_Level", "ESR", "C3", "C4",
]


def perform_rfecv(X_train, y_train, features_save_path):
    """Returns the fixed RFECV feature list (see SELECTED_FEATURES) and saves it."""
    missing = [f for f in SELECTED_FEATURES if f not in X_train.columns]
    if missing:
        raise ValueError(f"Training data is missing expected features: {missing}")

    selected_features = list(SELECTED_FEATURES)
    joblib.dump(selected_features, features_save_path)
    return selected_features
