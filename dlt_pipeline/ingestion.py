import dlt
import pandas as pd

# 1. Khoudi l'data mn l'fichier s'hih 
def load_medical_data():
    # SMYA DYAL L'FICHIER KHASS TKOUN BHAL LI 3NDEK F'DOSSIER DATA
    file_path = "data/Complete_Updated_Autoimmune_Disorder_Dataset2.csv"
    df = pd.read_csv(file_path)
    return df.to_dict(orient="records")

if __name__ == "__main__":

    # 2. Configurer l'pipeline
    pipeline = dlt.pipeline(
        pipeline_name="autoimmune_pipeline",
        # Hna fin gha n'diro l'path s'hih f'west destination
        destination=dlt.destinations.duckdb("duckdb/autoimmune_pipeline.duckdb"),
        dataset_name="raw_medical_data"
    )

    # 3. Run l'pipeline
    load_info = pipeline.run(
        load_medical_data(), 
        table_name="patients", 
        write_disposition="replace" 
    )
    print(load_info)