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

CMD ["dagster", "dev", "-f", "orchestration.py", "-h", "0.0.0.0", "-p", "3000"]