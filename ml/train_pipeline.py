import os
import json
import joblib
import logging
import mlflow
import mlflow.sklearn
from mlflow import MlflowClient
from mlflow.models import infer_signature
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
ENCODER_DIR = os.path.join(BASE_DIR, "encoder")

# MLflow configuration. Set MLFLOW_TRACKING_URI to point at a shared server
# (e.g. http://mlflow:5000); otherwise a local SQLite store in ml/mlflow.db is
# used with artifacts under ml/mlruns (both git-ignored).
_LOCAL_TRACKING_URI = "sqlite:///" + os.path.join(BASE_DIR, "mlflow.db").replace(os.sep, "/")
_LOCAL_ARTIFACT_ROOT = "file:///" + os.path.join(BASE_DIR, "mlruns").replace(os.sep, "/")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", _LOCAL_TRACKING_URI)
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT_NAME", "autoimmune-classification")
REGISTERED_MODEL_NAME = os.getenv("MLFLOW_MODEL_NAME", "autoimmune-classifier")
CHAMPION_ALIAS = "champion"


def composite_score(metrics):
    """Single number used to pick the champion: mean of balanced accuracy and weighted F1."""
    return (metrics["balanced_accuracy"] + metrics["f1_weighted"]) / 2.0


def track_candidate(name, model, metrics):
    """Logs one candidate model as a nested MLflow run."""
    with mlflow.start_run(run_name=name, nested=True):
        mlflow.set_tag("model_type", name)
        mlflow.log_params(model.get_params())
        mlflow.log_metrics(metrics)
        mlflow.log_metric("composite_score", composite_score(metrics))


def main():
    logger.info("Starting ML Training Pipeline...")

    # Ensure artifact directories exist
    for dir_path in ["scalers", "features", "models", "encoder"]:
        os.makedirs(os.path.join(BASE_DIR, dir_path), exist_ok=True)

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    if mlflow.get_experiment_by_name(MLFLOW_EXPERIMENT) is None:
        # Pin the artifact folder only for the local store; a remote server manages its own.
        artifact_location = _LOCAL_ARTIFACT_ROOT if MLFLOW_TRACKING_URI == _LOCAL_TRACKING_URI else None
        mlflow.create_experiment(MLFLOW_EXPERIMENT, artifact_location=artifact_location)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    logger.info(f"MLflow tracking URI: {MLFLOW_TRACKING_URI} | experiment: {MLFLOW_EXPERIMENT}")

    with mlflow.start_run(run_name="train_pipeline") as parent_run:
        # 1. Ingestion
        logger.info(f"Loading data from DuckDB at {DB_PATH}")
        X, y = load_data_from_duckdb(DB_PATH, table_name="main_marts.ml_patients_dataset")
        mlflow.log_params({
            "data_source": "main_marts.ml_patients_dataset",
            "n_rows": len(X),
            "n_raw_features": X.shape[1],
        })

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
        mlflow.log_param("n_selected_features", len(selected_features))
        mlflow.log_dict({"features": selected_features}, "selected_features.json")

        # Filter original splits down to selected features
        X_train_rfe = X_train[selected_features]
        X_test_rfe = X_test[selected_features]

        # 5. Final Scaling (Generating the artifact for FastAPI)
        logger.info("Generating final production scaler on selected features...")
        X_train_rfe_scaled, X_test_rfe_scaled = scale_data(X_train_rfe, X_test_rfe, SCALER_PATH)

        # 6. Balancing the Training Set
        logger.info("Balancing training data using SMOTEENN...")
        X_train_rfe_balanced, y_train_rfe_balanced = balance_training_data(X_train_rfe_scaled, y_train)
        mlflow.log_params({
            "test_size": 0.2,
            "balancing": "SMOTEENN",
            "n_train": len(X_train_rfe),
            "n_train_balanced": len(X_train_rfe_balanced),
            "n_test": len(X_test_rfe),
        })

        # 7. Model Training
        logger.info("Training candidate models...")
        rf_model = train_random_forest(X_train_rfe_balanced, y_train_rfe_balanced, RF_MODEL_PATH)

        logger.info("Training Support Vector Classifier (SVC)...")
        svc_model = train_svc(X_train_rfe_balanced, y_train_rfe_balanced, SVC_MODEL_PATH)

        # 8. Evaluation
        logger.info("Evaluating models on the test set...")
        rf_metrics = evaluate_model(rf_model, X_test_rfe_scaled, y_test)
        svc_metrics = evaluate_model(svc_model, X_test_rfe_scaled, y_test)

        rf_composite = composite_score(rf_metrics)
        svc_composite = composite_score(svc_metrics)

        logger.info(f"RF Composite Score: {rf_composite:.4f}")
        logger.info(f"SVC Composite Score: {svc_composite:.4f}")

        track_candidate("RandomForestClassifier", rf_model, rf_metrics)
        track_candidate("SVC", svc_model, svc_metrics)

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
            "num_features": len(selected_features),
            "mlflow_run_id": parent_run.info.run_id,
        }

        with open(METADATA_PATH, "w") as f:
            json.dump(metadata, f, indent=4)

        # 11. Log champion + supporting artifacts to MLflow and register it
        mlflow.set_tag("champion_model", champion_name)
        mlflow.log_metrics({f"champion_{k}": v for k, v in champion_metrics.items()})
        mlflow.log_metric("champion_composite_score", metadata["composite_score"])
        mlflow.log_artifact(SCALER_PATH, artifact_path="preprocessing")
        mlflow.log_artifact(FEATURES_PATH, artifact_path="preprocessing")
        mlflow.log_artifacts(ENCODER_DIR, artifact_path="encoder")
        mlflow.log_artifact(METADATA_PATH)

        input_example = X_test_rfe_scaled.head(5)
        signature = infer_signature(input_example, champion_model.predict(input_example))
        model_info = mlflow.sklearn.log_model(
            champion_model,
            name="model",
            signature=signature,
            input_example=input_example,
            registered_model_name=REGISTERED_MODEL_NAME,
            # MLflow 3 stores sklearn models with skops; tree-based models need this opt-in.
            skops_trusted_types=["sklearn.tree._tree.Tree"],
        )

        client = MlflowClient()
        version = model_info.registered_model_version
        client.set_registered_model_alias(REGISTERED_MODEL_NAME, CHAMPION_ALIAS, version)
        client.set_model_version_tag(REGISTERED_MODEL_NAME, version, "model_type", champion_name)
        logger.info(
            f"Registered {REGISTERED_MODEL_NAME} v{version} with alias '{CHAMPION_ALIAS}' "
            f"(run_id={parent_run.info.run_id})"
        )

    logger.info(f"Production model and metadata successfully written to {PROD_MODEL_PATH}")
    logger.info("Pipeline completed successfully! All artifacts are ready for the API.")

if __name__ == "__main__":
    main()
