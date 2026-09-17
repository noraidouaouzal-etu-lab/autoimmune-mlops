import os
import json
import joblib
import logging
from src.data_loader import load_data_from_duckdb
from src.preprocess import split_data, scale_data, balance_training_data
from src.select_features import perform_rfecv
from src.train import train_random_forest, train_svc
from src.evaluate import evaluate_model

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define paths (Resolving relative to this file)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "dataops", "data", "duckdb", "autoimmune.duckdb") # Adjust based on actual volume mount

# Artifact paths
SCALER_PATH = os.path.join(BASE_DIR, "scalers", "rfe_features_scaler.pkl")
FEATURES_PATH = os.path.join(BASE_DIR, "features", "rfecv_features.pkl")
RF_MODEL_PATH = os.path.join(BASE_DIR, "models", "rfe_rf_model.pkl")
SVC_MODEL_PATH = os.path.join(BASE_DIR, "models", "rfe_svc_model.pkl")

def main():
    logger.info("Starting ML Training Pipeline...")

    # Ensure artifact directories exist
    for dir_path in ["scalers", "features", "models", "encoder"]:
        os.makedirs(os.path.join(BASE_DIR, dir_path), exist_ok=True)

    # 1. Ingestion
    logger.info(f"Loading data from DuckDB at {DB_PATH}")
    X, y = load_data_from_duckdb(DB_PATH, table_name="main_marts.ml_patients_dataset")
    
    # 2. Split
    logger.info("Splitting data into train/test sets...")
    X_train, X_test, y_train, y_test = split_data(X, y)

    # 3. Initial Scaling (For Feature Selection)
    logger.info("Performing initial scaling for RFECV...")
    # Using a temporary scaler just for the feature selection phase
    temp_scaler_path = os.path.join(BASE_DIR, "scalers", "temp_scaler.pkl")
    X_train_scaled, X_test_scaled = scale_data(X_train, X_test, temp_scaler_path)

    # 4. Feature Selection (RFECV)
    logger.info("Running Recursive Feature Elimination (RFECV)...")
    selected_features = perform_rfecv(X_train_scaled, y_train, FEATURES_PATH)
    logger.info(f"Selected {len(selected_features)} optimal features.")

    # Filter original splits down to selected features
    X_train_rfe = X_train[selected_features]
    X_test_rfe = X_test[selected_features]

    # 5. Final Scaling (Generating the artifact for FastAPI)
    logger.info("Generating final production scaler on selected features...")
    X_train_rfe_scaled, X_test_rfe_scaled = scale_data(X_train_rfe, X_test_rfe, SCALER_PATH)

    # 6. Balancing the Training Set
    logger.info("Balancing training data using SMOTEENN...")
    X_train_rfe_balanced, y_train_rfe_balanced = balance_training_data(X_train_rfe_scaled, y_train)

    # 7. Model Training
    logger.info("Training candidate models...")
    rf_model = train_random_forest(X_train_rfe_balanced, y_train_rfe_balanced, RF_MODEL_PATH)
    
    logger.info("Training Support Vector Classifier (SVC)...")
    svc_model = train_svc(X_train_rfe_balanced, y_train_rfe_balanced, SVC_MODEL_PATH)

    # 8. Evaluation
    logger.info("Evaluating models on the test set...")
    rf_metrics = evaluate_model(rf_model, X_test_rfe_scaled, y_test)
    svc_metrics = evaluate_model(svc_model, X_test_rfe_scaled, y_test)

    rf_composite = (rf_metrics["balanced_accuracy"] + rf_metrics["f1_weighted"]) / 2.0
    svc_composite = (svc_metrics["balanced_accuracy"] + svc_metrics["f1_weighted"]) / 2.0

    logger.info(f"RF Composite Score: {rf_composite:.4f}")
    logger.info(f"SVC Composite Score: {svc_composite:.4f}")

    # 9. Model Champion Selection
    if rf_composite >= svc_composite:
        champion_model = rf_model
        champion_name = "RandomForestClassifier"
        champion_metrics = rf_metrics
    else:
        champion_model = svc_model
        champion_name = "SVC"
        champion_metrics = svc_metrics

    logger.info(f"Champion model selected: {champion_name}")

    # 10. Save the production model and metadata
    PROD_MODEL_PATH = os.path.join(BASE_DIR, "models", "production_model.pkl")
    METADATA_PATH = os.path.join(BASE_DIR, "models", "model_metadata.json")

    joblib.dump(champion_model, PROD_MODEL_PATH)

    metadata = {
        "model_type": champion_name,
        "composite_score": max(rf_composite, svc_composite),
        "metrics": champion_metrics,
        "num_features": len(selected_features)
    }

    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=4)

    logger.info(f"Production model and metadata successfully written to {PROD_MODEL_PATH}")
    logger.info("Pipeline completed successfully! All artifacts are ready for the API.")

if __name__ == "__main__":
    main()
