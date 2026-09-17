import argparse
import json
import os
import time
from datetime import datetime, timezone

import requests

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
HEALTH_LOG_FILE = os.path.join(_THIS_DIR, "logs", "health.log")
os.makedirs(os.path.dirname(HEALTH_LOG_FILE), exist_ok=True)

DEFAULT_URL = "http://localhost:8000"
HEALTH_PATH = "/health"


def probe_once(base_url: str, timeout: float = 5.0) -> dict:
    """Send one health probe and return a structured result."""
    url = base_url.rstrip("/") + HEALTH_PATH
    start = time.perf_counter()
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "up": False,
        "status_code": None,
        "response_time_ms": None,
        "detail": None,
    }
    try:
        resp = requests.get(url, timeout=timeout)
        result["response_time_ms"] = round((time.perf_counter() - start) * 1000, 2)
        result["status_code"] = resp.status_code
        result["up"] = resp.status_code == 200
        try:
            result["detail"] = resp.json()
        except Exception:
            result["detail"] = resp.text[:200]
    except requests.exceptions.RequestException as exc:
        result["response_time_ms"] = round((time.perf_counter() - start) * 1000, 2)
        result["detail"] = f"unreachable: {exc.__class__.__name__}"
    return result


def _append_log(result: dict) -> None:
    with open(HEALTH_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


def compute_uptime(window: int | None = None) -> dict:
    """Compute uptime % from the health log (optionally last `window` probes)."""
    if not os.path.exists(HEALTH_LOG_FILE):
        return {"probes": 0, "uptime_pct": None, "avg_response_ms": None}
    rows = []
    with open(HEALTH_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if window:
        rows = rows[-window:]
    if not rows:
        return {"probes": 0, "uptime_pct": None, "avg_response_ms": None}
    up = sum(1 for r in rows if r.get("up"))
    resp_times = [r["response_time_ms"] for r in rows if r.get("response_time_ms") is not None]
    return {
        "probes": len(rows),
        "uptime_pct": round(100 * up / len(rows), 2),
        "avg_response_ms": round(sum(resp_times) / len(resp_times), 2) if resp_times else None,
        "last_status": "UP" if rows[-1].get("up") else "DOWN",
        "last_check": rows[-1].get("timestamp"),
    }


def run_loop(base_url: str, interval: int) -> None:
    print(f"[health_monitor] polling {base_url}{HEALTH_PATH} every {interval}s "
          f"(Ctrl+C to stop). Log -> {HEALTH_LOG_FILE}")
    try:
        while True:
            result = probe_once(base_url)
            _append_log(result)
            state = "UP  " if result["up"] else "DOWN"
            rt = result["response_time_ms"]
            print(f"[{result['timestamp']}] {state} ({rt} ms)")
            time.sleep(interval)
    except KeyboardInterrupt:
        stats = compute_uptime()
        print(f"\n[health_monitor] stopped. Uptime this session: "
              f"{stats['uptime_pct']}% over {stats['probes']} probes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Health monitor for the prediction API.")
    parser.add_argument("--url", default=DEFAULT_URL, help="Base URL of the API.")
    parser.add_argument("--interval", type=int, default=15, help="Seconds between probes.")
    parser.add_argument("--once", action="store_true", help="Run a single probe and exit.")
    args = parser.parse_args()

    if args.once:
        r = probe_once(args.url)
        _append_log(r)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        run_loop(args.url, args.interval)
