FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY monitoring/requirements.txt ./monitoring/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r monitoring/requirements.txt

COPY monitoring/ ./monitoring/

RUN chmod +x monitoring/run_monitoring.sh
ENV PYTHONPATH=/app

CMD ["./monitoring/run_monitoring.sh"]