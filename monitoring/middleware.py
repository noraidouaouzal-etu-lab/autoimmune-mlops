
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse

from monitoring.logging_config import get_logger

logger = get_logger("api")

# ---------------------------------------------------------------------------
# In-memory metrics counters 
# ---------------------------------------------------------------------------
METRICS = {
    "requests_total": 0,
    "requests_by_status": {},   # e.g. {"200": 120, "400": 3}
    "predict_requests_total": 0,
    "predict_errors_total": 0,
    "latency_sum_ms": 0.0,
    "latency_count": 0,
}


class MonitoringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        start = time.perf_counter()

        try:
            response: Response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:  # unexpected server error
            latency_ms = (time.perf_counter() - start) * 1000
            _record(request.url.path, 500, latency_ms)
            logger.error(
                "unhandled request error",
                extra={"extra_data": {
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                    "latency_ms": round(latency_ms, 2),
                    "error": str(exc),
                }},
            )
            raise

        latency_ms = (time.perf_counter() - start) * 1000
        _record(request.url.path, status_code, latency_ms)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-ms"] = f"{latency_ms:.2f}"

        logger.info(
            "request",
            extra={"extra_data": {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "latency_ms": round(latency_ms, 2),
            }},
        )
        return response


def _record(path: str, status_code: int, latency_ms: float) -> None:
    METRICS["requests_total"] += 1
    key = str(status_code)
    METRICS["requests_by_status"][key] = METRICS["requests_by_status"].get(key, 0) + 1
    METRICS["latency_sum_ms"] += latency_ms
    METRICS["latency_count"] += 1
    if path.rstrip("/").endswith("/predict") or path == "/predict":
        METRICS["predict_requests_total"] += 1
        if status_code >= 400:
            METRICS["predict_errors_total"] += 1


async def metrics_endpoint(request: Request) -> PlainTextResponse:
    """Expose metrics in Prometheus text exposition format at GET /metrics."""
    avg_latency = (
        METRICS["latency_sum_ms"] / METRICS["latency_count"]
        if METRICS["latency_count"] else 0.0
    )
    lines = [
        "# HELP app_requests_total Total HTTP requests handled.",
        "# TYPE app_requests_total counter",
        f"app_requests_total {METRICS['requests_total']}",
        "# HELP app_predict_requests_total Total /predict requests.",
        "# TYPE app_predict_requests_total counter",
        f"app_predict_requests_total {METRICS['predict_requests_total']}",
        "# HELP app_predict_errors_total Total failed /predict requests.",
        "# TYPE app_predict_errors_total counter",
        f"app_predict_errors_total {METRICS['predict_errors_total']}",
        "# HELP app_request_latency_ms_avg Average request latency in ms.",
        "# TYPE app_request_latency_ms_avg gauge",
        f"app_request_latency_ms_avg {avg_latency:.2f}",
    ]
    for status, count in sorted(METRICS["requests_by_status"].items()):
        lines.append(f'app_requests_by_status{{code="{status}"}} {count}')
    return PlainTextResponse("\n".join(lines) + "\n")
