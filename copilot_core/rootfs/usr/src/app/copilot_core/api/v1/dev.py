"""Developer-oriented debug endpoints.

Kept for MVP parity with previous scaffold.
"""

import io
import json
import os
import re
import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, send_file

from diagnostics_contract import build_bundle_zip

bp = Blueprint("dev", __name__)

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401

DEV_LOG_MAX_CACHE_DEFAULT = 200

# Privacy-first sanitation for dev logs (best-effort).
_RE_JWT = re.compile(r"(?<![A-Za-z0-9_-])(eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})")
_RE_BEARER = re.compile(r"(?i)(bearer\s+)(\S+)")
_RE_URL_CREDS = re.compile(r"(?i)(https?://)([^\s:/]+):([^\s@/]+)@")

_TO_REDACT_KEYS = {
    "token",
    "auth_token",
    "access_token",
    "refresh_token",
    "password",
    "api_key",
    "key",
    "secret",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _sanitize_str(s: str, *, max_chars: int = 4000) -> str:
    s = _RE_URL_CREDS.sub(r"\1**REDACTED**:**REDACTED**@", s)
    s = _RE_BEARER.sub(r"\1**REDACTED**", s)
    s = _RE_JWT.sub("**REDACTED_JWT**", s)
    if len(s) > max_chars:
        s = s[: max_chars - 50] + "...(truncated)..."
    return s


def _sanitize_payload(obj):
    """Best-effort sanitation for dev log payloads.

    Privacy-first: avoid persisting obvious secrets.
    """

    if isinstance(obj, str):
        return _sanitize_str(obj)

    if isinstance(obj, dict):
        out = {}
        for k, v in list(obj.items())[:200]:
            ks = str(k)
            if ks.lower() in _TO_REDACT_KEYS:
                out[ks] = "**REDACTED**" if v else ""
            else:
                out[ks] = _sanitize_payload(v)
        return out

    if isinstance(obj, list):
        return [_sanitize_payload(v) for v in obj[:200]]

    return obj


def _resolve_writable_dev_log_path(preferred_path: str) -> str:
    """Resolve a writable dev log path with fallback outside add-on runtime."""
    global _DEV_LOG_PATH_OVERRIDE
    fallback_dir = os.environ.get("COPILOT_DEV_LOG_DIR", "/tmp")
    candidates = [
        preferred_path,
        os.path.join(fallback_dir, "dev_logs.jsonl"),
    ]
    for candidate in candidates:
        try:
            os.makedirs(os.path.dirname(candidate), exist_ok=True)
            _DEV_LOG_PATH_OVERRIDE = candidate
            return candidate
        except OSError:
            continue
    _DEV_LOG_PATH_OVERRIDE = preferred_path
    return preferred_path


def _dev_log_path() -> str:
    if _DEV_LOG_PATH_OVERRIDE:
        return _DEV_LOG_PATH_OVERRIDE
    cfg = current_app.config.get("COPILOT_CFG")
    data_dir = getattr(cfg, "data_dir", "/data")
    preferred_path = os.path.join(data_dir, "dev_logs.jsonl")
    return _resolve_writable_dev_log_path(preferred_path)


# In-memory ring buffer of recent dev logs.
_DEV_LOG_CACHE: list[dict] = []
_DEV_LOG_CACHE_LOADED = False
_DEV_LOG_PATH_OVERRIDE: str | None = None


def _ensure_dev_log_cache_loaded() -> None:
    """Load last dev logs into memory.

    Must run inside an application context (uses current_app).
    """

    global _DEV_LOG_CACHE_LOADED
    if _DEV_LOG_CACHE_LOADED:
        return
    _DEV_LOG_CACHE_LOADED = True

    path = _dev_log_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()[-DEV_LOG_MAX_CACHE_DEFAULT :]
        for line in lines:
            try:
                _DEV_LOG_CACHE.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return


def _append_dev_log(entry: dict) -> None:
    path = _dev_log_path()
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        fallback = _resolve_writable_dev_log_path(
            os.path.join(os.environ.get("COPILOT_DEV_LOG_DIR", "/tmp"), "dev_logs.jsonl")
        )
        with open(fallback, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    max_cache = DEV_LOG_MAX_CACHE_DEFAULT
    try:
        cfg = current_app.config.get("COPILOT_CFG")
        max_cache = int(getattr(cfg, "dev_log_cache_max", DEV_LOG_MAX_CACHE_DEFAULT))
    except Exception:
        pass

    _DEV_LOG_CACHE.append(entry)
    if len(_DEV_LOG_CACHE) > max_cache:
        del _DEV_LOG_CACHE[: len(_DEV_LOG_CACHE) - max_cache]


@bp.post("/dev/logs")
def ingest_dev_logs():
    _ensure_dev_log_cache_loaded()
    payload = request.get_json(silent=True) or {}
    payload = _sanitize_payload(payload)
    entry = {"received": _now_iso(), "payload": payload}

    try:
        _append_dev_log(entry)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, "stored": True})


@bp.get("/dev/status")
def dev_status():
    _ensure_dev_log_cache_loaded()
    cfg = current_app.config.get("COPILOT_CFG")
    ver = getattr(cfg, "version", "?")
    token_set = bool(getattr(cfg, "auth_token", "") or "")

    return jsonify(
        {
            "ok": True,
            "time": _now_iso(),
            "version": ver,
            "auth": {"enabled": token_set},
            "dev_logs": {
                "cache_count": len(_DEV_LOG_CACHE),
                "max_cache_default": DEV_LOG_MAX_CACHE_DEFAULT,
                "path": os.path.basename(_dev_log_path()),
            },
            "error_registry": {
                "unauthorized": {"title": "Unauthorized"},
                "bad_request": {"title": "Bad request"},
                "internal": {"title": "Internal error"},
            },
        }
    )


@bp.get("/dev/support_bundle")
def dev_support_bundle():
    """Download a privacy-first diagnostics bundle ZIP.

    Query params:
      - level=minimal|standard|deep (default: standard)
      - from_ts_ms / to_ts_ms (optional; clamped per level)
      - incident_id / module (optional; stored in manifest focus)
    """

    _ensure_dev_log_cache_loaded()
    cfg = current_app.config.get("COPILOT_CFG")
    ver = getattr(cfg, "version", "?")

    level = str(request.args.get("level", "standard") or "standard").strip().lower()
    if level not in ("minimal", "standard", "deep"):
        level = "standard"

    now = _now_ms()
    max_window_ms = {
        "minimal": 60 * 60 * 1000,
        "standard": 6 * 60 * 60 * 1000,
        "deep": 48 * 60 * 60 * 1000,
    }[level]

    def _parse_int(v):
        try:
            return int(v)
        except Exception:
            return None

    from_ts_ms = _parse_int(request.args.get("from_ts_ms"))
    to_ts_ms = _parse_int(request.args.get("to_ts_ms"))

    if to_ts_ms is None:
        to_ts_ms = now
    to_ts_ms = min(to_ts_ms, now)

    if from_ts_ms is None:
        from_ts_ms = to_ts_ms - max_window_ms

    # Clamp to max window.
    if to_ts_ms - from_ts_ms > max_window_ms:
        from_ts_ms = to_ts_ms - max_window_ms

    focus: dict[str, str] = {}
    incident_id = str(request.args.get("incident_id", "") or "").strip()
    module = str(request.args.get("module", "") or "").strip()
    if incident_id:
        focus["incident_id"] = _sanitize_str(incident_id, max_chars=200)
    if module:
        focus["module"] = _sanitize_str(module, max_chars=200)

    zip_bytes, manifest = build_bundle_zip(
        level=level,
        window_from_ts_ms=from_ts_ms,
        window_to_ts_ms=to_ts_ms,
        core_version=str(ver),
        dev_log_items=_DEV_LOG_CACHE[-DEV_LOG_MAX_CACHE_DEFAULT :],
        focus=focus or None,
    )

    filename = f"diagnostics_{manifest.get('created_ts_ms','')}_{level}.zip"
    bio = io.BytesIO(zip_bytes)
    bio.seek(0)
    return send_file(
        bio,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


@bp.get("/dev/logs")
def get_dev_logs():
    _ensure_dev_log_cache_loaded()
    try:
        limit = int(request.args.get("limit", "50"))
    except Exception:
        limit = 50
    limit = max(1, min(limit, DEV_LOG_MAX_CACHE_DEFAULT))

    return jsonify({"ok": True, "count": min(limit, len(_DEV_LOG_CACHE)), "items": _DEV_LOG_CACHE[-limit:]})


@bp.get("/capabilities")
def get_capabilities():
    """Core capabilities endpoint for HA Integration health checks.

    Returns available Core features and API version.
    """
    cfg = current_app.config.get("COPILOT_CFG")
    ver = getattr(cfg, "version", "?")

    return jsonify({
        "ok": True,
        "version": ver,
        "capabilities": [
            "events",
            "candidates",
            "neurons",
            "mood",
            "graph",
            "habitus",
            "weather",
            "unifi",
            "energy",
            "vector",
            "tags",
            "voice_context",
            "user_preferences",
            "knowledge_graph",
            "collective_intelligence",
        ],
        "api_version": "v1",
        "features": {
            "brain_graph": True,
            "habitus_mining": True,
            "neural_pipeline": True,
            "multi_user_learning": True,
            "federated_learning": True,
        },
        "modules": {
            "events": {
                "enabled": True,
                "persist": getattr(cfg, "events_persist", False) if hasattr(cfg, "events_persist") else False,
                "cache_max": getattr(cfg, "events_cache_max", 500) if hasattr(cfg, "events_cache_max") else 500,
                "idempotency": {
                    "supported": True,
                    "ttl_seconds": getattr(cfg, "events_idempotency_ttl_seconds", 1200) if hasattr(cfg, "events_idempotency_ttl_seconds") else 1200,
                    "lru_max": getattr(cfg, "events_idempotency_lru_max", 10000) if hasattr(cfg, "events_idempotency_lru_max") else 10000,
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
                "persist": getattr(cfg, "candidates_persist", False) if hasattr(cfg, "candidates_persist") else False,
                "max": getattr(cfg, "candidates_max", 500) if hasattr(cfg, "candidates_max") else 500,
            },
            "mood": {
                "enabled": True,
                "window_seconds": getattr(cfg, "mood_window_seconds", 3600) if hasattr(cfg, "mood_window_seconds") else 3600,
            },
            "brain_graph": {
                "enabled": True,
                "persist": getattr(cfg, "brain_graph_persist", True) if hasattr(cfg, "brain_graph_persist") else True,
                "json_path": getattr(cfg, "brain_graph_json_path", "/data/brain_graph.json") if hasattr(cfg, "brain_graph_json_path") else "/data/brain_graph.json",
                "nodes_max": getattr(cfg, "brain_graph_nodes_max", 500) if hasattr(cfg, "brain_graph_nodes_max") else 500,
                "edges_max": getattr(cfg, "brain_graph_edges_max", 1500) if hasattr(cfg, "brain_graph_edges_max") else 1500,
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
        }
    })
