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

    # Initialize security middleware (rate limiting, security headers, logging)
    init_security_middleware(app)

    # Register API modules
    app.register_blueprint(api_v1)

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

    # Predictive Analytics API endpoints (/api/v1/predictive/analytics/*)
    try:
        from copilot_core.api.v1.predictive_analytics import analytics_bp
        app.register_blueprint(analytics_bp)
        logging.getLogger(__name__).info("Predictive Analytics API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Predictive Analytics API blueprint")

    # Multi-Zone Coordination API endpoints (/api/v1/multizone/*)
    try:
        from copilot_core.api.v1.multizone import multizone_bp
        app.register_blueprint(multizone_bp)
        logging.getLogger(__name__).info("Multi-Zone Coordination API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Multi-Zone Coordination API blueprint")

    # Canonical Action Closure API endpoints (/api/v1/action-closures/*)
    try:
        from copilot_core.api.v1.action_closure import action_closure_bp
        app.register_blueprint(action_closure_bp)
        logging.getLogger(__name__).info("Action Closure API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Action Closure API blueprint")

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

    # Synapse Layer API endpoints (/api/v1/synapse/*, /api/v1/presence/*)
    try:
        from copilot_core.api.v1.synapse_api import bp as synapse_bp
        app.register_blueprint(synapse_bp)
        logging.getLogger(__name__).info("Synapse Layer API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Synapse Layer API blueprint")

    # Zone Presence Hold API endpoints (/api/v1/presence/zones/*/hold)
    try:
        from copilot_core.api.v1.zone_presence_hold import create_blueprint as create_zone_presence_hold_bp
        app.register_blueprint(create_zone_presence_hold_bp())
        logging.getLogger(__name__).info("Zone Presence Hold API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Zone Presence Hold API blueprint")

    # Zone Presence Hold Notifications API endpoints (/api/v1/presence/holds/notifications)
    try:
        from copilot_core.api.v1.zone_presence_hold_notifications import setup_routes as setup_zone_presence_hold_notifications
        setup_zone_presence_hold_notifications(app)
        logging.getLogger(__name__).info("Zone Presence Hold Notifications API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Zone Presence Hold Notifications API blueprint")

    # Zone Presence Hold Scheduler API endpoints (/api/v1/presence/holds/scheduler/*)
    try:
        from copilot_core.api.v1.zone_presence_hold_scheduler import blueprint as zone_presence_hold_scheduler_bp
        app.register_blueprint(zone_presence_hold_scheduler_bp)
        logging.getLogger(__name__).info("Zone Presence Hold Scheduler API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Zone Presence Hold Scheduler API blueprint")

    # Zone Presence Hold Analytics API endpoints (/api/v1/presence/holds/analytics/*)
    try:
        from copilot_core.api.v1.presence_hold_analytics import create_blueprint as create_presence_hold_analytics_bp
        app.register_blueprint(create_presence_hold_analytics_bp())
        logging.getLogger(__name__).info("Zone Presence Hold Analytics API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Zone Presence Hold Analytics API blueprint")

    # Music/Media Analytics API endpoints (/api/v1/media/analytics/*)
    try:
        from copilot_core.api.v1.music_analytics import music_analytics_bp
        app.register_blueprint(music_analytics_bp)
        logging.getLogger(__name__).info("Music/Media Analytics API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Music/Media Analytics API blueprint")

    # Health Analytics API endpoints (/api/v1/health/analytics/*)
    try:
        from copilot_core.api.v1.health_analytics import create_blueprint as create_health_analytics_bp
        app.register_blueprint(create_health_analytics_bp())
        logging.getLogger(__name__).info("Health Analytics API registered")
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Health Analytics API blueprint")

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
        return jsonify({"ok": True, "time": _now_iso(), "port": int(os.environ.get("PORT", "8909"))})

    @app.get("/version")
    def version():
        return jsonify({"version": cfg.version, "time": _now_iso()})

    @app.get("/api/v1/status")
    def api_status():
        return jsonify(
            {
                "ok": True,
                "time": _now_iso(),
                "version": cfg.version,
                "port": int(os.environ.get("PORT", "8909")),
            }
        )

    @app.get("/api/v1/capabilities")
    def capabilities():
        return jsonify(
            {
                "ok": True,
                "time": _now_iso(),
                "version": cfg.version,
                "modules": {
                    "events": {
                        "enabled": True,
                        "persist": cfg.events_persist,
                        "cache_max": cfg.events_cache_max,
                        "idempotency": {
                            "supported": True,
                            "ttl_seconds": cfg.events_idempotency_ttl_seconds,
                            "lru_max": cfg.events_idempotency_lru_max,
                            "key_sources": [
                                "Idempotency-Key header",
                                "idempotency_key payload field",
                                "event_id payload field",
                                "id payload field",
                            ],
                        },
                    },
                    "candidates": {
                        "enabled": True,
                        "persist": cfg.candidates_persist,
                        "max": cfg.candidates_max,
                    },
                    "mood": {"enabled": True, "window_seconds": cfg.mood_window_seconds},
                    "brain_graph": {
                        "enabled": True,
                        "persist": cfg.brain_graph_persist,
                        "json_path": cfg.brain_graph_json_path,
                        "nodes_max": cfg.brain_graph_nodes_max,
                        "edges_max": cfg.brain_graph_edges_max,
                        "feeding_enabled": True,
                    },
                    "vector_store": {
                        "enabled": True,
                        "version": "0.1.0",
                        "description": "Vector operations for semantic search and embeddings",
                        "endpoints": [
                            "/api/v1/vector/store",
                            "/api/v1/vector/search",
                            "/api/v1/vector/get/:id",
                            "/api/v1/vector/delete/:id",
                            "/api/v1/vector/stats"
                        ]
                    },
                    "dashboard": {
                        "enabled": True,
                        "version": "0.1.0",
                        "description": "Dashboard data endpoints",
                        "endpoints": [
                            "/api/v1/dashboard/brain-summary"
                        ]
                    },
                    "search": {
                        "enabled": True,
                        "version": "1.0.0",
                        "description": "Quick search for entities, automations, scripts, scenes, and services",
                        "endpoints": [
                            "/api/v1/search",
                            "/api/v1/search/entities",
                            "/api/v1/search/stats",
                            "/api/v1/search/index"
                        ]
                    },
                    "notifications": {
                        "enabled": True,
                        "version": "1.0.0",
                        "description": "Push notification system for alerts, mood changes, and suggestions",
                        "endpoints": [
                            "/api/v1/notifications/send",
                            "/api/v1/notifications",
                            "/api/v1/notifications/subscribe",
                            "/api/v1/notifications/subscriptions"
                        ]
                    },
                    "voice_context": {
                        "enabled": True,
                        "version": "1.0.0",
                        "description": "Voice assistant integration for mood-based context",
                        "endpoints": [
                            "/api/v1/voice_context"
                        ]
                    },
                    "anomaly_detection": {
                        "enabled": True,
                        "version": "1.0.0",
                        "description": "ML-based anomaly detection for sensor patterns using Isolation Forest",
                        "endpoints": [
                            "/api/v1/anomaly/detect",
                            "/api/v1/anomaly/history",
                            "/api/v1/anomaly/sensor/:sensor_id/health",
                            "/api/v1/anomaly/train",
                            "/api/v1/anomaly/model/status",
                            "/api/v1/anomaly/model/save",
                            "/api/v1/anomaly/model/load",
                            "/api/v1/anomaly/model/versions",
                            "/api/v1/anomaly/compare",
                            "/api/v1/anomaly/store/stats"
                        ],
                        "features": [
                            "Isolation Forest anomaly detection",
                            "Incremental learning (partial_fit)",
                            "Per-sensor anomaly scoring",
                            "Critical alert integration",
                            "Model persistence and versioning"
                        ]
                    },
                    "multihome": {
                        "enabled": True,
                        "version": "1.0.0",
                        "description": "Multi-home synchronization for multiple locations (Hauptwohnung, Ferienhaus, Büro)",
                        "endpoints": [
                            "/api/v1/multihome/homes",
                            "/api/v1/multihome/homes/<home_id>",
                            "/api/v1/multihome/config/diff/<source>/<target>",
                            "/api/v1/multihome/config/sync",
                            "/api/v1/multihome/state/diff/<home1>/<home2>",
                            "/api/v1/multihome/state/sync",
                            "/api/v1/multihome/location/sync",
                            "/api/v1/multihome/climate/preheat",
                            "/api/v1/multihome/conflicts",
                            "/api/v1/multihome/conflicts/<id>/resolve",
                            "/api/v1/multihome/status",
                            "/api/v1/multihome/operations"
                        ],
                        "features": [
                            "Secure synchronization between multiple homes",
                            "Location-aware automations (e.g., Ferienhaus vorheizen)",
                            "Encrypted communication between instances",
                            "Conflict resolution (last_write_wins, primary_wins, merge, manual)",
                            "Configuration and state synchronization",
                            "Climate and lighting scene sync"
                        ]
                    },
                },
            }
        )

    @app.before_request
    def _auth_middleware():
        # Use centralized auth logic from security.py
        # Allowlisted paths (no auth required)
        allowlist = {"/", "/health", "/version", "/api/v1/status", "/api/v1/docs", "/api/v1/docs/openapi.yaml"}

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
