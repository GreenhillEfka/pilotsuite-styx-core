import json
import os
from dataclasses import dataclass
import logging
from datetime import datetime, timezone
from typing import Any

from flask import Flask, jsonify, request

from copilot_core.api.v1.blueprint import api_v1
from copilot_core.api.security import validate_token, is_auth_required
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

    # Register API modules
    app.register_blueprint(api_v1)

    # Standalone Onyx bridge endpoints (/api/v1/onyx/*)
    try:
        from copilot_core.api.v1.onyx_bridge import onyx_bridge_bp
        app.register_blueprint(onyx_bridge_bp)
    except Exception:
        logging.getLogger(__name__).exception("Failed to register Onyx bridge blueprint")

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
