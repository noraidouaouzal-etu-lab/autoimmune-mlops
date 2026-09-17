import os
import sys

import pandas as pd
import streamlit as st

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from monitoring.metrics import build_dashboard_data
from monitoring.health_monitor import probe_once, _append_log, DEFAULT_URL

BACKEND_URL = os.getenv("BACKEND_URL", DEFAULT_URL)

with st.sidebar:
    st.markdown("### Monitoring")
    st.caption("Autoimmune Disease Prediction — service observability")
    api_url = st.text_input("API base URL", BACKEND_URL)

st.set_page_config(
    page_title="Autoimmune ML • Monitoring",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Styling — clinical instrument panel: dark slate, single teal signal accent,
# monospace numerics so metrics read like a readout, not a marketing card.
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');

  :root {
    --bg: #0d1420;
    --panel: #131c2b;
    --panel-line: #1e2c40;
    --ink: #e6edf6;
    --muted: #7f92ab;
    --signal: #2dd4bf;      /* teal — the one accent */
    --warn: #f4b740;
    --alert: #f2645a;
    --ok: #2dd4bf;
  }

  .stApp { background: var(--bg); color: var(--ink); }
  * { font-family: 'IBM Plex Sans', sans-serif; }

  .mono { font-family: 'IBM Plex Mono', monospace; }

  .panel {
    background: var(--panel);
    border: 1px solid var(--panel-line);
    border-radius: 10px;
    padding: 1.1rem 1.25rem;
    height: 100%;
  }
  .panel h3 {
    font-size: .72rem; letter-spacing: .14em; text-transform: uppercase;
    color: var(--muted); margin: 0 0 .6rem 0; font-weight: 600;
  }
  .readout {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 2.1rem; font-weight: 600; line-height: 1; color: var(--ink);
  }
  .readout small { font-size: .9rem; color: var(--muted); font-weight: 500; }
  .sub { color: var(--muted); font-size: .82rem; margin-top: .35rem; }

  .pill {
    display: inline-block; padding: .18rem .6rem; border-radius: 999px;
    font-size: .72rem; font-weight: 600; letter-spacing: .04em;
    font-family: 'IBM Plex Mono', monospace;
  }
  .pill-ok    { background: rgba(45,212,191,.14); color: var(--ok); border:1px solid rgba(45,212,191,.4); }
  .pill-warn  { background: rgba(244,183,64,.14); color: var(--warn); border:1px solid rgba(244,183,64,.4); }
  .pill-alert { background: rgba(242,100,90,.14);  color: var(--alert); border:1px solid rgba(242,100,90,.4); }

  .headbar {
    display:flex; align-items:baseline; gap:.9rem;
    border-bottom: 1px solid var(--panel-line); padding-bottom: .7rem; margin-bottom: 1.1rem;
  }
  .headbar .title { font-size: 1.35rem; font-weight: 600; }
  .headbar .tag { color: var(--muted); font-size: .8rem; font-family:'IBM Plex Mono',monospace; }

  [data-testid="stSidebar"] { background: #0a111c; border-right: 1px solid var(--panel-line); }
  .stDataFrame { border: 1px solid var(--panel-line); border-radius: 8px; }
  section.main > div { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)


def _pill(status: str) -> str:
    s = (status or "").upper()
    if s in ("UP", "STABLE", "OK"):
        return f'<span class="pill pill-ok">{s or "—"}</span>'
    if s in ("WATCH", "DEGRADED"):
        return f'<span class="pill pill-warn">{s}</span>'
    if s in ("DOWN", "DRIFT", "ALERT"):
        return f'<span class="pill pill-alert">{s}</span>'
    return f'<span class="pill pill-warn">{s or "N/A"}</span>'


# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Monitoring")
    st.caption("Autoimmune Disease Prediction — service observability")
    api_url = st.text_input("API base URL", DEFAULT_URL)
    if st.button("Probe health now", use_container_width=True):
        res = probe_once(api_url)
        _append_log(res)
        st.success(f"Probe: {'UP' if res['up'] else 'DOWN'} ({res['response_time_ms']} ms)")
    if st.button("Refresh metrics", use_container_width=True):
        st.rerun()
    st.markdown("---")
    st.caption("Data sources")
    st.caption("• logs/predictions.log\n\n• logs/health.log\n\n• reports/drift_report.json")

data = build_dashboard_data()
api = data["api_metrics"]
health = data["health"]
drift = data["drift"]
model = data["model_metrics"]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
overall = drift.get("overall_status", "NOT_RUN")
st.markdown(
    f'<div class="headbar">'
    f'<span class="title">Service Monitoring</span>'
    f'<span class="tag">generated {data["generated_at"][:19]}Z</span>'
    f'<span style="margin-left:auto">drift {_pill(overall)}</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Row 1 — headline readouts
# ---------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)

with c1:
    up = health.get("uptime_pct")
    last = health.get("last_status", "N/A")
    st.markdown(
        f'<div class="panel"><h3>Availability</h3>'
        f'<div class="readout">{up if up is not None else "—"}<small> %</small></div>'
        f'<div class="sub">{_pill(last)} · {health.get("probes",0)} probes</div></div>',
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f'<div class="panel"><h3>Predictions served</h3>'
        f'<div class="readout mono">{api["total_predictions"]}</div>'
        f'<div class="sub">{api["errors"]} errors · {api["error_rate_pct"]}% error rate</div></div>',
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f'<div class="panel"><h3>Latency p95</h3>'
        f'<div class="readout mono">{api["p95_latency_ms"]}<small> ms</small></div>'
        f'<div class="sub">p50 {api["p50_latency_ms"]} · p99 {api["p99_latency_ms"]} ms</div></div>',
        unsafe_allow_html=True,
    )

with c4:
    n_drift = len(drift.get("drifted_features", []))
    n_watch = len(drift.get("watch_features", []))
    st.markdown(
        f'<div class="panel"><h3>Feature drift</h3>'
        f'<div class="readout mono">{n_drift}<small> / {n_watch} watch</small></div>'
        f'<div class="sub">over {drift.get("n_samples",0)} samples · {_pill(overall)}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Row 2 — latency trend + class distribution
# ---------------------------------------------------------------------------
c5, c6 = st.columns([1.4, 1])

with c5:
    st.markdown('<div class="panel"><h3>Latency trend (last 50)</h3>', unsafe_allow_html=True)
    trend = api.get("latency_trend", [])
    if trend:
        st.line_chart(pd.DataFrame({"latency_ms": trend}), height=220, color="#2dd4bf")
    else:
        st.caption("No predictions logged yet.")
    st.markdown('</div>', unsafe_allow_html=True)

with c6:
    st.markdown('<div class="panel"><h3>Predicted class distribution</h3>', unsafe_allow_html=True)
    dist = model.get("class_distribution", {})
    if dist:
        df_dist = pd.DataFrame(
            {"class": list(dist.keys()), "count": list(dist.values())}
        ).set_index("class").sort_values("count", ascending=False)
        st.bar_chart(df_dist, height=220, color="#2dd4bf")
    else:
        st.caption("No successful predictions yet.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Row 3 — drift detail table
# ---------------------------------------------------------------------------
st.markdown('<div class="panel"><h3>Per-feature drift (PSI / KS)</h3>', unsafe_allow_html=True)
feats = drift.get("features", {})
if feats:
    rows = []
    for name, s in feats.items():
        rows.append({
            "feature": name,
            "PSI": s.get("psi"),
            "KS p-value": s.get("ks_pvalue"),
            "ref mean": s.get("ref_mean"),
            "current mean": s.get("cur_mean"),
            "status": s.get("status"),
        })
    df = pd.DataFrame(rows).sort_values("PSI", ascending=False)

    def _style(row):
        color = {"DRIFT": "#f2645a", "WATCH": "#f4b740", "STABLE": "#2dd4bf"}.get(row["status"], "")
        return [f"color: {color}" if col == "status" else "" for col in row.index]

    st.dataframe(df.style.apply(_style, axis=1), use_container_width=True, hide_index=True)
    st.caption("PSI thresholds — <0.10 stable · 0.10–0.25 watch · >0.25 drift. "
               "KS drift flagged when p < 0.05.")
else:
    st.caption("Drift check not run yet. Build the reference and run a check "
               "(see monitoring/README).")
st.markdown('</div>', unsafe_allow_html=True)
