Write-Host "`n=== 1. Wiping old environment ===" -ForegroundColor Cyan
docker compose down -v

Write-Host "`n=== 2. Building fresh images ===" -ForegroundColor Cyan
docker compose build --no-cache

Write-Host "`n=== 5. Starting Dagster ===" -ForegroundColor Cyan
docker compose up -d dagster
Write-Host "Waiting 10 seconds for Dagster to initialize..."
Start-Sleep -Seconds 10

Write-Host "`n=== 6. Generating DuckDB Database ===" -ForegroundColor Cyan
docker exec ml-dagster mkdir -p /app/data/duckdb
docker exec ml-dagster dagster asset materialize -f orchestration.py --select "*"

Write-Host "`n=== 7. Starting Backend, Frontend, and Observability Stack ===" -ForegroundColor Cyan
docker compose up -d

Write-Host "`n=== 8. Streaming Backend Logs (Ctrl+C to exit logs) ===" -ForegroundColor Green
docker logs -f ml-backend