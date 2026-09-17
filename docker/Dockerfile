FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the pieces the serving app needs
COPY api/        ./api/
COPY monitoring/ ./monitoring/
COPY ml/models/   ./ml/models/
COPY ml/scalers/  ./ml/scalers/
COPY ml/encoder/  ./ml/encoder/
COPY ml/features/ ./ml/features/

EXPOSE 8000
# api.main:app resolves ml/ and monitoring/ relative to the repo root (/app)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
