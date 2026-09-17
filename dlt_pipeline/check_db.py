import duckdb

# Connecter l'database
conn = duckdb.connect("duckdb/autoimmune_pipeline.duckdb")

# Choufi les tables li t'creeyaw
print(conn.execute("SHOW TABLES").fetchall())

# Choufi l'uwwal dyal l'data
print(conn.execute("SELECT * FROM raw_medical_data.patients LIMIT 5").df())