import dlt
import pandas as pd
import os

# Configure Paths
RAW_DATA_PATH = "./data/raw_csv/"
DUCKDB_PATH = "./data/duckdb/autoimmune.duckdb"

# Create a DLT pipeline
pipeline = dlt.pipeline(
    pipeline_name="autoimmune_ingestion",
    destination=dlt.destinations.duckdb(credentials=DUCKDB_PATH),
    dataset_name="raw_medical_data"
)

# 1. Khoudi l'data mn l'fichier s'hih 
def load_medical_data(filename):
    file_path = os.path.join(RAW_DATA_PATH, filename)
    if not os.path.exists(file_path):
        print(f"Fichier introuvable: {file_path}")
        return None
    df = pd.read_csv(file_path)
    return df.to_dict(orient="records")

@dlt.resource(name="patients", write_disposition="replace")
def get_medical_data():
    # Load the medical data from the CSV file
    data = load_medical_data("Complete_Updated_Autoimmune_Disorder_Dataset2.csv")
    if data and len(data) > 0:
        yield data

if __name__ == "__main__":
    print("[INFO] Démarrage de l'ingestion dlt vers DuckDB...")

    load_info = pipeline.run(
        get_medical_data(), 
    )
    
    print("\n[SUCCESS] Ingestion terminée avec succès !")
    print(load_info)