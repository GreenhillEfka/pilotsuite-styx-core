"""
PilotSuite Core — Styx

Main Application Entry Point.
Delegates service initialization and blueprint registration to core_setup.py.
"""

import json
import logging as _logging
import os
import time
import threading as _threading
import uuid

from flask import Flask, request, jsonify, send_from_directory, g, render_template
from flask_compress import Compress
from waitress import serve

from copilot_core.api.security import require_token, validate_token, get_auth_token
from copilot_core.api.api_version import API_VERSION, parse_accept_version, get_deprecation_info
from copilot_core.core_setup import init_services, register_blueprints
from copilot_core.versioning import get_runtime_version

APP_VERSION = get_runtime_version()

_main_logger = _logging.getLogger(__name__)


def _load_options_json(path: str = "/data/options.json") -> dict:
    """Lade Add-on Konfiguration aus options.json (Home Assistant Supervisor)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Startup pre-flight validation (v3.6.0)
# ---------------------------------------------------------------------------

def _preflight_check() -> dict:
    """Run pre-flight checks before starting the server.

    Returns a dict with check results (all non-fatal — logged as warnings).
    """
    import requests as http_req
    checks = {}

    # 1) /data writable?
    try:
        os.makedirs("/data", exist_ok=True)
        test_path = "/data/.preflight_test"
        with open(test_path, "w") as f:
            f.write("ok")
        os.remove(test_path)
        checks["data_writable"] = True
    except Exception:
        checks["data_writable"] = False
        _main_logger.warning("PRE-FLIGHT: /data is NOT writable — persistence will fail")

    # 2) HA Supervisor reachable?
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if ha_token:
        try:
            r = http_req.get(
                "http://supervisor/core/api/",
                headers={"Authorization": f"Bearer {ha_token}"},
                timeout=5,
            )
            checks["ha_supervisor"] = r.ok
        except Exception:
            checks["ha_supervisor"] = False
            _main_logger.warning("PRE-FLIGHT: HA Supervisor unreachable")
    else:
        checks["ha_supervisor"] = None  # No token = development mode

    # 3) Ollama reachable?
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    try:
        r = http_req.get(f"{ollama_url}/api/tags", timeout=5)
        checks["ollama"] = r.ok
        if r.ok:
            models = r.json().get("models", [])
            checks["ollama_models"] = len(models)
    except Exception:
        checks["ollama"] = False
        _main_logger.warning("PRE-FLIGHT: Ollama unreachable at %s", ollama_url)

    return checks


DEV_LOG_PATH = "/data/dev_logs.jsonl"
DEV_LOG_MAX_CACHE = 200

app = Flask(__name__)

# Initialize compression for API responses
Compress(app)
app.config['COMPRESS_MIMETYPES'] = ['application/json', 'text/html']
app.config['COMPRESS_LEVEL'] = 6
app.config['COMPRESS_MIN_SIZE'] = 500
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB upload limit

# ---------------------------------------------------------------------------
# Request timing middleware + correlation IDs (v3.6.0)
# ---------------------------------------------------------------------------

_REQUEST_METRICS: dict = {"total": 0, "slow": 0, "errors": 0, "by_endpoint": {}}
_METRICS_LOCK = _threading.Lock()
SLOW_REQUEST_THRESHOLD = 2.0  # seconds


@app.before_request
def _before_request():
    g.start_time = time.time()
    g.request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    g.api_version = parse_accept_version(request.headers.get("Accept-Version"))


@app.after_request
def _after_request(response):
    duration = time.time() - getattr(g, "start_time", time.time())
    req_id = getattr(g, "request_id", "-")
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time"] = f"{duration:.3f}s"
    response.headers["X-API-Version"] = getattr(g, "api_version", API_VERSION)

    # Deprecation warnings (v5.0.0)
    deprecation = get_deprecation_info(request.path)
    if deprecation:
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = deprecation.get("sunset", "")
        if deprecation.get("successor"):
            response.headers["Link"] = f'<{deprecation["successor"]}>; rel="successor-version"'

    endpoint = request.endpoint or request.path
    status = response.status_code

    with _METRICS_LOCK:
        _REQUEST_METRICS["total"] += 1
        if duration >= SLOW_REQUEST_THRESHOLD:
            _REQUEST_METRICS["slow"] += 1
            _main_logger.warning(
                "SLOW REQUEST [%s] %s %s -> %d (%.2fs)",
                req_id, request.method, request.path, status, duration,
            )
        if status >= 500:
            _REQUEST_METRICS["errors"] += 1

        ep_key = f"{request.method} {endpoint}"
        ep = _REQUEST_METRICS["by_endpoint"].setdefault(ep_key, {
            "count": 0, "total_ms": 0, "max_ms": 0, "errors": 0
        })
        ep["count"] += 1
        ep["total_ms"] += int(duration * 1000)
        ep["max_ms"] = max(ep["max_ms"], int(duration * 1000))
        if status >= 500:
            ep["errors"] += 1

    return response


# ---------------------------------------------------------------------------
# Service initialization
# ---------------------------------------------------------------------------

_options = _load_options_json()

# Run pre-flight checks
_preflight_results = _preflight_check()
_main_logger.info("Pre-flight check results: %s", json.dumps(_preflight_results))

try:
    _services = init_services(config=_options)
except Exception:
    _main_logger.exception("CRITICAL: init_services failed — starting with empty services")
    _services = {}

try:
    register_blueprints(app, _services)
except Exception:
    _main_logger.exception("CRITICAL: register_blueprints failed")

# Store startup info
_STARTUP_TIME = time.time()
app.config["STARTUP_TIME"] = _STARTUP_TIME
app.config["PREFLIGHT"] = _preflight_results

# In-memory ring buffer of recent dev logs (thread-safe).
_DEV_LOG_CACHE: list[dict] = []
_DEV_LOG_LOCK = _threading.Lock()


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _append_dev_log(entry: dict) -> None:
    import json
    os.makedirs(os.path.dirname(DEV_LOG_PATH), exist_ok=True)
    with open(DEV_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    with _DEV_LOG_LOCK:
        _DEV_LOG_CACHE.append(entry)
        if len(_DEV_LOG_CACHE) > DEV_LOG_MAX_CACHE:
            del _DEV_LOG_CACHE[: len(_DEV_LOG_CACHE) - DEV_LOG_MAX_CACHE]


def _load_dev_log_cache() -> None:
    import json
    try:
        with open(DEV_LOG_PATH, "r", encoding="utf-8") as fh:
            lines = fh.readlines()[-DEV_LOG_MAX_CACHE:]
        for line in lines:
            try:
                _DEV_LOG_CACHE.append(json.loads(line))
            except Exception:
                continue
    except FileNotFoundError:
        return
    except Exception:
        return


_load_dev_log_cache()


TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')


@app.get("/")
def index():
    """Serve PilotSuite Dashboard (ingress panel)."""
    return render_template(
        "dashboard.html",
        dashboard_auth_token=get_auth_token() or "",
    )


@app.get("/api/v1/cards/<path:filename>")
def serve_card(filename):
    """Serve Lovelace custom card JavaScript files.

    These are loaded as Lovelace resources by the HACS integration:
      /api/v1/cards/pilotsuite-cards.js
    """
    cards_dir = os.path.join(STATIC_DIR, 'cards')
    response = send_from_directory(cards_dir, filename)
    response.headers['Cache-Control'] = 'public, max-age=3600'
    response.headers['Content-Type'] = 'application/javascript'
    return response


@app.get("/health")
def health():
    """Basic liveness probe — always returns 200 if the process is alive."""
    return jsonify({"ok": True, "time": _now_iso()})


@app.get("/ready")
def readiness():
    """Readiness probe — returns 200 only if critical services are initialized."""
    services = app.config.get("COPILOT_SERVICES", {})
    brain_ok = services.get("brain_graph_service") is not None
    memory_ok = services.get("conversation_memory") is not None
    conv_enabled = str(os.environ.get("CONVERSATION_ENABLED", "true")).lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    ollama_ok = True
    if conv_enabled:
        try:
            import requests as http_req
            r = http_req.get(f"{ollama_url}/api/tags", timeout=2)
            ollama_ok = bool(r.ok)
        except Exception:
            ollama_ok = False

    ready = brain_ok and memory_ok and ollama_ok
    status = 200 if ready else 503
    return jsonify({
        "ready": ready,
        "brain_graph": brain_ok,
        "conversation_memory": memory_ok,
        "ollama_required": conv_enabled,
        "ollama": ollama_ok,
        "ollama_url": ollama_url,
        "vector_store": services.get("vector_store") is not None,
        "uptime_s": int(time.time() - _STARTUP_TIME),
    }), status


@app.get("/api/v1/health/deep")
def deep_health():
    """Deep health check — tests all services and external dependencies."""
    import requests as http_req

    checks = {}

    # 1. Internal services
    services = app.config.get("COPILOT_SERVICES", {})
    for svc_name in [
        "brain_graph_service", "conversation_memory", "vector_store",
        "mood_service", "habitus_service", "neuron_manager",
        "web_search_service", "module_registry",
    ]:
        checks[svc_name] = services.get(svc_name) is not None

    # 2. HA Supervisor
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if ha_token:
        try:
            r = http_req.get(
                "http://supervisor/core/api/",
                headers={"Authorization": f"Bearer {ha_token}"},
                timeout=5,
            )
            checks["ha_supervisor"] = r.ok
        except Exception:
            checks["ha_supervisor"] = False
    else:
        checks["ha_supervisor"] = None

    # 3. Ollama
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    try:
        r = http_req.get(f"{ollama_url}/api/tags", timeout=5)
        checks["ollama"] = r.ok
    except Exception:
        checks["ollama"] = False

    # 4. SQLite databases
    for db_label, db_path in [
        ("conversation_memory_db", "/data/conversation_memory.db"),
        ("vector_store_db", "/data/vector_store.db"),
        ("shopping_db", "/data/shopping_reminders.db"),
    ]:
        checks[db_label] = os.path.exists(db_path)

    # 5. Disk usage
    try:
        import shutil
        usage = shutil.disk_usage("/data")
        checks["disk_free_mb"] = int(usage.free / (1024 * 1024))
        checks["disk_used_pct"] = int(usage.used / usage.total * 100)
    except Exception:
        checks["disk_free_mb"] = -1

    # 6. Request metrics
    checks["request_metrics"] = {
        "total": _REQUEST_METRICS["total"],
        "slow": _REQUEST_METRICS["slow"],
        "errors": _REQUEST_METRICS["errors"],
    }

    # 7. Circuit breakers (v3.6.0)
    try:
        from copilot_core.circuit_breaker import get_all_breaker_status
        checks["circuit_breakers"] = get_all_breaker_status()
    except Exception:
        checks["circuit_breakers"] = []

    all_ok = all(
        v is True for k, v in checks.items()
        if isinstance(v, bool) and k not in ("ha_supervisor",)
    )

    return jsonify({
        "healthy": all_ok,
        "version": APP_VERSION,
        "uptime_s": int(time.time() - _STARTUP_TIME),
        "checks": checks,
        "time": _now_iso(),
    }), 200 if all_ok else 503


@app.get("/api/v1/health/metrics")
def request_metrics():
    """Request timing metrics — endpoint latencies, slow requests, error rates."""
    with _METRICS_LOCK:
        top_slow = sorted(
            _REQUEST_METRICS["by_endpoint"].items(),
            key=lambda x: x[1]["max_ms"],
            reverse=True,
        )[:10]
    return jsonify({
        "total_requests": _REQUEST_METRICS["total"],
        "slow_requests": _REQUEST_METRICS["slow"],
        "errors": _REQUEST_METRICS["errors"],
        "slow_threshold_s": SLOW_REQUEST_THRESHOLD,
        "top_endpoints_by_latency": {k: v for k, v in top_slow},
        "uptime_s": int(time.time() - _STARTUP_TIME),
    })


@app.get("/version")
def version():
    return jsonify({
        "name": "Styx",
        "suite": "PilotSuite",
        "version": APP_VERSION,
        "time": _now_iso(),
    })


@app.post("/api/v1/echo")
@require_token
def echo():
    payload = request.get_json(silent=True) or {}
    return jsonify({"time": _now_iso(), "received": payload})


@app.post("/api/v1/dev/logs")
@require_token
def ingest_dev_logs():
    payload = request.get_json(silent=True) or {}
    entry = {
        "received": _now_iso(),
        "payload": payload,
    }

    try:
        _append_dev_log(entry)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, "stored": True})


@app.get("/api/v1/dev/logs")
@require_token
def get_dev_logs():
    try:
        limit = int(request.args.get("limit", "50"))
    except Exception:
        limit = 50
    limit = max(1, min(limit, DEV_LOG_MAX_CACHE))

    return jsonify({
        "ok": True,
        "count": min(limit, len(_DEV_LOG_CACHE)),
        "items": _DEV_LOG_CACHE[-limit:],
    })


# ---------------------------------------------------------------------------
# Dashboard API Endpoints (v7.11.0) - Always available fallback
# ---------------------------------------------------------------------------

def _get_brain_graph_service():
    """Get Brain Graph service instance."""
    try:
        from copilot_core.brain_graph.provider import get_graph_service
        return get_graph_service()
    except Exception:
        return None


@app.get("/api/v1/dashboard/brain-summary")
@require_token
def dashboard_brain_summary():
    """Get brain graph summary for dashboard display.
    
    Returns node counts, edge counts, top nodes, and top edges.
    """
    brain_service = _get_brain_graph_service()
    
    if not brain_service:
        return jsonify({
            "ok": False,
            "error": "Brain Graph service not available",
            "time": _now_iso(),
        }), 503
    
    try:
        state = brain_service.export_state(limit_nodes=50, limit_edges=100)
        
        nodes = state.get("nodes", [])
        edges = state.get("edges", [])
        
        kind_counts = {}
        for node in nodes:
            kind = node.get("kind", "unknown")
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
        
        type_counts = {}
        for edge in edges:
            edge_type = edge.get("type", "unknown")
            type_counts[edge_type] = type_counts.get(edge_type, 0) + 1
        
        sorted_nodes = sorted(nodes, key=lambda n: n.get("score", 0), reverse=True)
        top_nodes = sorted_nodes[:10]
        
        sorted_edges = sorted(edges, key=lambda e: e.get("weight", 0), reverse=True)
        top_edges = sorted_edges[:10]
        
        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "summary": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "nodes_by_kind": kind_counts,
                "edges_by_type": type_counts,
            },
            "top_nodes": [
                {
                    "id": n.get("id"),
                    "label": n.get("label"),
                    "kind": n.get("kind"),
                    "score": round(n.get("score", 0), 6),
                }
                for n in top_nodes
            ],
            "top_edges": [
                {
                    "id": e.get("id"),
                    "from": e.get("from"),
                    "to": e.get("to"),
                    "type": e.get("type"),
                    "weight": round(e.get("weight", 0), 6),
                }
                for e in top_edges
            ],
        })
        
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "time": _now_iso(),
        }), 500


@app.get("/api/v1/dashboard/health")
@require_token
def dashboard_health():
    """Dashboard module health check."""
    brain_ok = _get_brain_graph_service() is not None
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "module": "dashboard",
        "version": "7.11.0",
        "features": [
            "brain_graph_summary",
            "node_statistics",
            "edge_statistics",
        ],
        "integrations": {
            "brain_graph": "ok" if brain_ok else "unavailable",
        },
        "status": "active",
        "endpoints": [
            "/api/v1/dashboard/brain-summary",
            "/api/v1/dashboard/health",
        ],
    })


# ---------------------------------------------------------------------------
# Hub API Fallback Endpoints (v7.11.0)
# ---------------------------------------------------------------------------

@app.get("/api/v1/hub/dashboard")
@require_token
def hub_dashboard():
    """Hub dashboard overview - falls back to basic data if Hub unavailable."""
    try:
        from copilot_core.hub.dashboard import DashboardHub
        dashboard = DashboardHub()
        overview = dashboard.get_overview()
        return jsonify({
            "ok": True,
            "layout": {
                "name": overview.layout.get("name"),
                "columns": overview.layout.get("columns"),
            },
            "widgets_count": len(overview.widgets),
            "summary": overview.summary,
            "alerts_count": overview.alerts_count,
        })
    except Exception as e:
        # Return minimal fallback
        return jsonify({
            "ok": True,
            "layout": {"name": "default", "columns": 3},
            "widgets_count": 0,
            "summary": {},
            "alerts_count": 0,
            "fallback": True,
            "error": str(e)[:100],
        })


@app.get("/api/v1/hub/widget-types")
@require_token
def hub_widget_types():
    """Get available widget types."""
    try:
        from copilot_core.hub.dashboard import WIDGET_TYPES
        return jsonify({
            "ok": True,
            "widget_types": list(WIDGET_TYPES),
        })
    except Exception:
        return jsonify({
            "ok": True,
            "widget_types": [
                "energy_overview",
                "battery_status",
                "heat_pump_status",
                "weather_warnings",
                "mood_indicator",
                "system_health",
            ],
            "fallback": True,
        })


if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "8909"))
    _main_logger.info(
        "Starting PilotSuite v%s on %s:%d (pre-flight: %s)",
        APP_VERSION, host, port, json.dumps(_preflight_results),
    )
    serve(app, host=host, port=port)
