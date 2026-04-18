import json
import os
from dataclasses import dataclass
import logging
from datetime import datetime, timezone
from typing import Any

from flask import Flask, jsonify, request

from copilot_core.api.v1.blueprint import api_v1
from copilot_core.api.security import validate_token, is_auth_required
from copilot_core.api.middleware.security import init_security_middleware
from copilot_core.versioning import get_runtime_version


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_runtime_persistence_summary() -> dict[str, object]:
    persistence_paths = {
        "conversation_memory_db": os.environ.get("CONVERSATION_MEMORY_DB", "/data/conversation_memory.db"),
        "vector_store_db": os.environ.get("COPILOT_VECTOR_DB_PATH", "/data/vector_store.db"),
        "shopping_db": os.environ.get("SHOPPING_DB_PATH", "/data/shopping_reminders.db"),
    }
    summary: dict[str, object] = {}
    for label, db_path in persistence_paths.items():
        summary[f"{label}_path"] = db_path
        summary[f"{label}_accessible"] = os.path.exists(db_path)
    return summary


@dataclass(frozen=True)
class CopilotConfig:
    version: str = "0.0.0"

    # Logging
    log_level: str = "info"

    # Auth
    auth_token: str = ""

    # Storage locations (HA add-on has /data)
    data_dir: str = "/data"

    # Events: minimal persistence; defaults to memory-only.
    events_persist: bool = False
    events_jsonl_path: str = "/data/events.jsonl"
    events_cache_max: int = 500

    # Events: idempotency/deduping
    events_idempotency_ttl_seconds: int = 20 * 60
    events_idempotency_lru_max: int = 10_000

    # Candidates: minimal persistence; defaults to memory-only.
    candidates_persist: bool = False
    candidates_json_path: str = "/data/candidates.json"
    candidates_max: int = 500

    # Mood engine
    mood_window_seconds: int = 3600

    # Brain graph (v0.1)
    brain_graph_persist: bool = True
    brain_graph_json_path: str = "/data/brain_graph.json"
    brain_graph_nodes_max: int = 500
    brain_graph_edges_max: int = 1500


def _load_options_json(path: str = "/data/options.json") -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def _build_config() -> CopilotConfig:
    opts = _load_options_json()
    version = get_runtime_version()

    log_level = str(opts.get("log_level", "info") or "info").strip().lower()
    token = os.environ.get("COPILOT_AUTH_TOKEN", "").strip()
    if not token:
        token = str(opts.get("auth_token", "")).strip()

    data_dir = str(opts.get("data_dir", "/data"))

    events_persist = bool(opts.get("events_persist", False))
    events_jsonl_path = str(opts.get("events_jsonl_path", os.path.join(data_dir, "events.jsonl")))
    events_cache_max = int(opts.get("events_cache_max", 500))

    events_idempotency_ttl_seconds = int(opts.get("events_idempotency_ttl_seconds", 20 * 60))
    events_idempotency_lru_max = int(opts.get("events_idempotency_lru_max", 10_000))

    candidates_persist = bool(opts.get("candidates_persist", False))
    candidates_json_path = str(opts.get("candidates_json_path", os.path.join(data_dir, "candidates.json")))
    candidates_max = int(opts.get("candidates_max", 500))

    mood_window_seconds = int(opts.get("mood_window_seconds", 3600))

    brain_graph_persist = bool(opts.get("brain_graph_persist", True))
    brain_graph_json_path = str(opts.get("brain_graph_json_path", os.path.join(data_dir, "brain_graph.json")))
    brain_graph_nodes_max = int(opts.get("brain_graph_nodes_max", 500))
    brain_graph_edges_max = int(opts.get("brain_graph_edges_max", 1500))

    return CopilotConfig(
        version=version,
        log_level=log_level,
        auth_token=token,
        data_dir=data_dir,
        events_persist=events_persist,
        events_jsonl_path=events_jsonl_path,
        events_cache_max=max(1, min(events_cache_max, 10_000)),
        events_idempotency_ttl_seconds=max(10, min(events_idempotency_ttl_seconds, 24 * 3600)),
        events_idempotency_lru_max=max(0, min(events_idempotency_lru_max, 200_000)),
        candidates_persist=candidates_persist,
        candidates_json_path=candidates_json_path,
        candidates_max=max(1, min(candidates_max, 10_000)),
        mood_window_seconds=max(60, min(mood_window_seconds, 24 * 3600)),
        brain_graph_persist=brain_graph_persist,
        brain_graph_json_path=brain_graph_json_path,
        brain_graph_nodes_max=max(10, min(brain_graph_nodes_max, 10_000)),
        brain_graph_edges_max=max(10, min(brain_graph_edges_max, 50_000)),
    )


def _setup_logging(level: str) -> None:
    # Keep this intentionally simple; HA add-on base already manages log routing.
    lvl = logging.INFO
    if level in ("trace", "debug"):
        lvl = logging.DEBUG
    elif level == "info":
        lvl = logging.INFO
    elif level in ("warn", "warning"):
        lvl = logging.WARNING
    elif level == "error":
        lvl = logging.ERROR

    logging.basicConfig(
        level=lvl,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Reduce noise unless debugging.
    logging.getLogger("werkzeug").setLevel(lvl)
    logging.getLogger("waitress").setLevel(lvl)


def create_app() -> Flask:
    cfg = _build_config()
    _setup_logging(cfg.log_level)

    app = Flask(__name__)

    # Attach config to app (simple, explicit)
    app.config["COPILOT_CFG"] = cfg

    # Install the single voice runtime seam early so the voice blueprint can
    # resolve injected services instead of constructing them in the route layer.
    try:
        from copilot_core.voice.runtime_access import init_voice_runtime
        init_voice_runtime(app, app.config.get("COPILOT_SERVICES"))
    except Exception:
        logging.getLogger(__name__).exception("Failed to initialize voice runtime seam")

    # Initialize security middleware (rate limiting, security headers, logging)
    init_security_middleware(app)

    # Register API modules
    app.register_blueprint(api_v1)

    # Auth setup blueprint: /api/v1/auth/*
    # /setup-token is intentionally unauthenticated (1-Key-Flow seam for HA)
    try:
        from copilot_core.api.v1.auth import auth_bp
        app.register_blueprint(auth_bp)
        logging.getLogger(__name__).info("Auth blueprint registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Auth blueprint")

    # Full voice API surface (/api/v1/voice/*) is absolute-prefix and must be
    # registered directly on the app, not nested under api_v1.
    try:
        from copilot_core.api.v1.voice import bp as voice_bp
        app.register_blueprint(voice_bp)
        logging.getLogger(__name__).info("Voice API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Voice API blueprint")

    # Standalone Onyx bridge endpoints (/api/v1/onyx/*)
    try:
        from copilot_core.api.v1.onyx_bridge import onyx_bridge_bp
        app.register_blueprint(onyx_bridge_bp)
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Onyx bridge blueprint")

    # Anomaly Detection API endpoints (/api/v1/anomaly/*)
    try:
        from copilot_core.api.v1.anomaly import anomaly_bp
        app.register_blueprint(anomaly_bp, url_prefix="/api/v1")
        logging.getLogger(__name__).info("Anomaly Detection API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Anomaly Detection API blueprint")

    # Multi-Home Synchronization API endpoints (/api/v1/multihome/*)
    try:
        from copilot_core.api.v1.multihome import bp as multihome_bp
        app.register_blueprint(multihome_bp, url_prefix="/api/v1/multihome")
        logging.getLogger(__name__).info("Multi-Home Synchronization API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Multi-Home Synchronization API blueprint")

    # Module Control API endpoints (/api/v1/modules/*)
    try:
        from copilot_core.api.v1.module_control import module_control_bp
        app.register_blueprint(module_control_bp)
        logging.getLogger(__name__).info("Module Control API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Module Control API blueprint")

    # Security Configuration API endpoints (/api/v1/security/*)
    try:
        from copilot_core.api.v1.security import bp as security_bp
        app.register_blueprint(security_bp)
        logging.getLogger(__name__).info("Security Configuration API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Security Configuration API blueprint")

    # Predictive Automation API endpoints (/api/v1/predictive/*)
    try:
        from copilot_core.api.v1.predictive import predictive_bp
        app.register_blueprint(predictive_bp)
        logging.getLogger(__name__).info("Predictive Automation API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Predictive Automation API blueprint")

    # Rate Limit Configuration API is registered via api_v1 blueprint

    # MCP REST API endpoints (/api/v1/mcp/*)
    try:
        from copilot_core.api.v1.mcp import bp as mcp_bp
        app.register_blueprint(mcp_bp)
        logging.getLogger(__name__).info("MCP REST API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register MCP REST API blueprint")
    # Endpoints: /api/v1/rate-limit/*

    # Metrics API endpoints (/api/v1/metrics/*)
    # Registered via copilot_core.api.v1.blueprint (metrics_bp)
    logging.getLogger(__name__).info("Metrics API registered (via api_v1 blueprint)")

    # RAG Search API endpoints (/api/v1/rag/*)
    try:
        from copilot_core.api.v1.rag import bp as rag_bp
        app.register_blueprint(rag_bp)
        logging.getLogger(__name__).info("RAG Search API registered (v1 Flask blueprint)")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register RAG Search API blueprint")
    
    # RAG Search aiohttp-based endpoints (register Flask wrappers)
    try:
        from copilot_core.api.rag_search import register_rag_search_flask
        register_rag_search_flask(app)
        logging.getLogger(__name__).info("RAG Search API registered (aiohttp Flask wrappers)")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register RAG Search Flask wrappers")

    # Styx Chat API endpoints (/api/styx/*)
    try:
        from copilot_core.api.v1.styx_chat import bp as styx_chat_bp
        app.register_blueprint(styx_chat_bp)
        logging.getLogger(__name__).info("Styx Chat API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Styx Chat API blueprint")

    # Initialize Tags API v2 (FIX: Flask Blueprint rewrite)
    from copilot_core.tags.api import init_tags_api
    from copilot_core.tags import TagRegistry
    tags_registry = TagRegistry()
    init_tags_api(tags_registry)

    @app.get("/")
    def index():
        return (
            "PilotSuite Core Add-on\n"
            "Endpoints: /health, /ready, /version, /api/v1/*\n"
            "Modules: brain_graph, mood, habitus, candidates, conversation, calendar, shopping\n"
        )

    @app.get("/health")
    def health():
        # Include the port env for easier ops/debugging.
        from copilot_core.voice.voice_health import get_voice_health_block
        voice_block = get_voice_health_block()
        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "port": int(os.environ.get("PORT", "8909")),
            "voice": voice_block,
        })

    @app.get("/version")
    def version():
        return jsonify({"version": cfg.version, "time": _now_iso()})

    @app.get("/api/v1/status")
    def api_status():
        from copilot_core.voice.voice_health import get_voice_health_block
        return jsonify(
            {
                "ok": True,
                "time": _now_iso(),
                "version": cfg.version,
                "port": int(os.environ.get("PORT", "8909")),
                "voice": get_voice_health_block(),
                "persistence": _get_runtime_persistence_summary(),
            }
        )

    # `/api/v1/capabilities` is registered once via the nested api_v1/dev blueprint.
    # Keep the lightweight app factory on the same canonical capability surface
    # instead of shadow-registering a second handler here.

    @app.before_request
    def _auth_middleware():
        # Use centralized auth logic from security.py
        # Allowlisted paths (no auth required)
        allowlist = {"/", "/health", "/version", "/api/v1/status", "/api/v1/docs", "/api/v1/docs/openapi.yaml", "/api/v1/auth/setup-token"}

        if request.path in allowlist:
            return None

        if not validate_token(request):
            return jsonify({
                "error": "unauthorized",
                "message": "Valid X-Auth-Token header or Bearer token required"
            }), 401

        return None

    return app


def create_full_app(config: dict | None = None) -> Flask:
    """Create a Flask app with ALL blueprints registered (like production).

    Unlike ``create_app()`` which only registers the nested ``api_v1`` plus a
    handful of standalone blueprints, this factory mirrors ``main.py`` by
    calling ``init_services()`` and ``register_blueprints()`` from
    ``core_setup.py``.  This ensures integration tests cover the full
    production endpoint surface.

    Args:
        config: Optional configuration dict (forwarded to ``init_services``).

    Returns:
        Flask application with all services and blueprints wired.
    """
    import asyncio
    from copilot_core.core_setup import init_services, register_blueprints

    cfg = _build_config()
    _setup_logging(cfg.log_level)

    app = Flask(__name__)
    app.config["COPILOT_CFG"] = cfg
    app.config["TESTING"] = True

    # Initialize security middleware
    init_security_middleware(app)

    # Initialize services (async → sync bridge)
    try:
        services = asyncio.run(init_services(config=config or {}))
    except Exception:
        logging.getLogger(__name__).exception("init_services failed in full test app")
        services = {}

    # Register all production blueprints
    try:
        register_blueprints(app, services)
    except Exception:
        logging.getLogger(__name__).exception("register_blueprints failed in full test app")

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "time": _now_iso()})

    @app.get("/version")
    def version():
        return jsonify({"version": cfg.version, "time": _now_iso()})

    return app
