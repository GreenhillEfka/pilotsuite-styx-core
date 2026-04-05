"""Lightweight runtime config inspection API.

This surface intentionally exposes only non-secret summary data so the registry
contains a real Flask blueprint without leaking credentials.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import validate_token
from copilot_core.versioning import get_runtime_version

config_bp = Blueprint("config", __name__, url_prefix="/api/v1/config")

_PUBLIC_CONFIG_KEYS = (
    "DEBUG",
    "TESTING",
    "ENV",
    "APPLICATION_ROOT",
    "PREFERRED_URL_SCHEME",
)


@config_bp.before_request
def _require_auth():
    if not validate_token(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401


@config_bp.get("")
def get_config_summary():
    app_config = current_app.config
    services = app_config.get("COPILOT_SERVICES", {}) or {}

    return jsonify(
        {
            "ok": True,
            "version": get_runtime_version(),
            "config": {key: app_config.get(key) for key in _PUBLIC_CONFIG_KEYS if key in app_config},
            "service_count": len(services),
            "service_keys": sorted(str(key) for key in services.keys()),
        }
    )


@config_bp.get("/services")
def get_config_services():
    services = current_app.config.get("COPILOT_SERVICES", {}) or {}
    return jsonify(
        {
            "ok": True,
            "count": len(services),
            "services": sorted(str(key) for key in services.keys()),
        }
    )


__all__ = ["config_bp"]


# ── SLICE 147: Config API Expansion ─────────────────────────────────

@bp.post("/validate")
def config_validate():
    """Validate config without applying.
    
    Body:
    - config: Config object to validate
    
    Returns:
    - valid: true|false
    - errors: List of validation errors
    - warnings: List of warnings
    """
    data = request.get_json() or {}
    config = data.get("config")
    
    if config is None:
        return jsonify({
            "ok": False,
            "error": "Missing config"
        }), 400
    
    from copilot_core.config.validator import get_config_validator
    
    try:
        validator = get_config_validator()
        result = validator.validate(config)
        valid = result.get("valid", False)
        errors = result.get("errors", [])
        warnings = result.get("warnings", [])
    except Exception as e:
        _LOGGER.warning("Config validation failed: %s", e)
        valid = False
        errors = [str(e)]
        warnings = []
    
    return jsonify({
        "ok": True,
        "valid": valid,
        "errors": errors,
        "warnings": warnings
    })


@bp.get("/history")
def config_history():
    """Get config change history.
    
    Query params:
    - limit: Max entries (default 20)
    - days: Days to look back (default 30)
    """
    from copilot_core.config.store import get_config_store
    
    try:
        limit = int(request.args.get("limit", "20"))
    except (ValueError, TypeError):
        limit = 20
    
    try:
        days = int(request.args.get("days", "30"))
    except (ValueError, TypeError):
        days = 30
    
    limit = max(1, min(limit, 100))
    days = max(1, min(days, 365))
    
    try:
        store = get_config_store()
        history = store.get_history(limit=limit, days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get config history: %s", e)
        history = []
    
    return jsonify({
        "ok": True,
        "history": history,
        "count": len(history),
        "limit": limit,
        "days": days
    })


@bp.get("/history/<version_id>")
def config_get_version(version_id):
    """Get config at specific version.
    
    Returns the config snapshot at the given version ID.
    """
    from copilot_core.config.store import get_config_store
    
    try:
        store = get_config_store()
        config = store.get_version(version_id=version_id)
    except Exception as e:
        _LOGGER.warning("Failed to get config version: %s", e)
        config = None
    
    if not config:
        return jsonify({
            "ok": False,
            "error": "Version not found"
        }), 404
    
    return jsonify({
        "ok": True,
        "version_id": version_id,
        "config": config
    })


@bp.post("/rollback")
def config_rollback():
    """Rollback config to previous version.
    
    Requires admin token.
    
    Body:
    - version_id: Target version to rollback to
    """
    auth_error = _require_admin_mutation("CONFIG_ROLLBACK", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    version_id = data.get("version_id")
    
    if not version_id:
        return jsonify({
            "ok": False,
            "error": "Missing version_id"
        }), 400
    
    from copilot_core.config.store import get_config_store
    
    try:
        store = get_config_store()
        result = store.rollback_to(version_id=version_id)
        success = result.get("success", False)
    except Exception as e:
        _LOGGER.warning("Config rollback failed: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "version_id": version_id
    })
