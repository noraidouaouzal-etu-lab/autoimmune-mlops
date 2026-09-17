
import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(_THIS_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

APP_LOG_FILE = os.path.join(LOG_DIR, "app.log")
PREDICTION_LOG_FILE = os.path.join(LOG_DIR, "predictions.log")


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    """Format every log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach any structured "extra" fields passed via logger.info(..., extra={"extra_data": {...}})
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            payload.update(record.extra_data)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Logger factory (cached so we don't add duplicate handlers)
# ---------------------------------------------------------------------------
_configured_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str = "app") -> logging.Logger:
    """Return a configured JSON logger writing to console + rotating app.log."""
    if name in _configured_loggers:
        return _configured_loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = JsonFormatter()

    file_handler = RotatingFileHandler(
        APP_LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    _configured_loggers[name] = logger
    return logger


# ---------------------------------------------------------------------------
# Dedicated prediction logger (kept separate from app noise)
# ---------------------------------------------------------------------------
_prediction_logger: logging.Logger | None = None


def _get_prediction_logger() -> logging.Logger:
    global _prediction_logger
    if _prediction_logger is not None:
        return _prediction_logger

    logger = logging.getLogger("predictions")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = RotatingFileHandler(
        PREDICTION_LOG_FILE, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    _prediction_logger = logger
    return logger


def log_prediction(
    features: dict,
    prediction: str | None,
    latency_ms: float,
    status: str,
    error: str | None = None,
    request_id: str | None = None,
) -> None:
    """
    Record a single prediction event to predictions.log as JSON.

    This is the raw material for both the monitoring dashboard (latency,
    throughput, error rate, class distribution) and the drift detector
    (feature values over time).
    """
    logger = _get_prediction_logger()
    event = {
        "event": "prediction",
        "request_id": request_id,
        "status": status,
        "prediction": prediction,
        "latency_ms": round(float(latency_ms), 2),
        "features": features,
    }
    if error:
        event["error"] = error
    logger.info("prediction", extra={"extra_data": event})
