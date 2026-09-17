import duckdb
import pandas as pd
import os

def load_data_from_duckdb(db_path: str, table_name: str = "patients"):
    """Extracts the final mart table from DuckDB."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}")
    
    with duckdb.connect(db_path, read_only=True) as con:
        # Load directly into a Pandas DataFrame
        df = con.execute(f"SELECT * FROM {table_name}").df()
    
    # Split features and target as done in the notebook
    X = df.drop(columns=['diagnosis'])
    y = df['diagnosis']
    return X, y