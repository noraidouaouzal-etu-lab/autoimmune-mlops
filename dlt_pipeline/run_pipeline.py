import os
print("Démarrage de l'ingestion des données...")
os.system("python dlt_pipeline/ingestion.py")
print("Données chargées dans DuckDB avec succès !")