FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir uv --upgrade pip && \
    uv pip install --system --no-cache -r requirements.txt

COPY . .

# Point dbt to look for profiles.yml inside the dbt project folder
ENV DBT_PROFILES_DIR=/app/data_transform
ENV DAGSTER_HOME=/app/dagster_home
RUN mkdir -p $DAGSTER_HOME

# Generate the initial dbt manifest.json required by orchestration.py
RUN cd data_transform && dbt clean && dbt deps && dbt parse

EXPOSE 3000

# Autonomous Boot Sequence: Check for fully built marts -> Materialize if missing -> Start Webserver
CMD ["bash", "-c", "echo 'Checking if database and marts are fully built...'; if ! python -c \"import duckdb; duckdb.connect('/app/data/duckdb/autoimmune.duckdb', read_only=True).execute('SELECT 1 FROM main_marts.ml_patients_dataset')\" 2>/dev/null; then echo 'Final data marts not found! Auto-bootstrapping data pipeline...'; echo 'Step 1: Refreshing dbt dependencies...'; cd data_transform && dbt deps && dbt parse && cd ..; echo 'Step 2: Materializing Dagster assets...'; dagster asset materialize -f orchestration.py --select '*'; echo 'Data pipeline execution completed!'; else echo 'Database and marts are already fully built. Skipping bootstrap.'; fi; echo 'Starting Dagster Webserver...'; dagster-webserver -h 0.0.0.0 -p 3000 -f orchestration.py"]
