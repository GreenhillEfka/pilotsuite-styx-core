"""Authentication setup endpoints.

Provides a setup-token endpoint for the HA integration to auto-fetch
the active auth token during Zero Config / Quick Start setup.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from copilot_core.api.security import get_auth_token, get_token_source

_LOGGER = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.get("/setup-token")
def setup_token():
    """Return the active auth token for HA integration setup (1-Key-Flow).

    Exposes the token regardless of source (auto, options, env).
    This endpoint is intentionally unauthenticated — it is only reachable
    on the local network and enables seamless Zero Config integration.
    """
    source = get_token_source()

    if source == "none":
        return jsonify({
            "ok": False,
            "token": None,
            "source": "none",
            "message": "No token configured",
        })

    token = get_auth_token()
    if not token:
        return jsonify({
            "ok": False,
            "token": None,
            "source": source,
            "message": "Token could not be resolved",
        })

    _LOGGER.info(
        "Setup token requested — returning %s token (%s...%s)",
        source, token[:8], token[-4:],
    )
    return jsonify({"ok": True, "token": token, "source": source})


# ── SLICE 148: Auth API Expansion ─────────────────────────────────

@auth_bp.get("/sessions")
def auth_sessions():
    """List active auth sessions.
    
    Query params:
    - user_id: Filter by user (optional)
    - limit: Max sessions (default 50)
    """
    from copilot_core.auth.store import get_auth_store
    
    user_id = request.args.get("user_id")
    
    try:
        limit = int(request.args.get("limit", "50"))
    except (ValueError, TypeError):
        limit = 50
    
    limit = max(1, min(limit, 200))
    
    try:
        store = get_auth_store()
        sessions = store.list_sessions(user_id=user_id, limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to list sessions: %s", e)
        sessions = []
    
    return jsonify({
        "ok": True,
        "sessions": sessions,
        "count": len(sessions),
        "user_id": user_id,
        "limit": limit
    })


@auth_bp.delete("/sessions/<session_id>")
def auth_revoke_session(session_id):
    """Revoke an active session.
    
    Requires admin token.
    """
    auth_error = _require_admin_mutation("REVOKE_SESSION", "Admin token required")
    if auth_error:
        return auth_error
    
    from copilot_core.auth.store import get_auth_store
    
    try:
        store = get_auth_store()
        store.revoke_session(session_id=session_id)
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to revoke session: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "session_id": session_id
    })


@auth_bp.get("/api-keys")
def auth_api_keys():
    """List API keys.
    
    Query params:
    - user_id: Filter by user (optional)
    - active_only: true|false (default: true)
    """
    from copilot_core.auth.store import get_auth_store
    
    user_id = request.args.get("user_id")
    active_only = request.args.get("active_only", "true").lower() == "true"
    
    try:
        store = get_auth_store()
        keys = store.list_api_keys(user_id=user_id, active_only=active_only)
    except Exception as e:
        _LOGGER.warning("Failed to list API keys: %s", e)
        keys = []
    
    return jsonify({
        "ok": True,
        "api_keys": keys,
        "count": len(keys),
        "user_id": user_id,
        "active_only": active_only
    })


@auth_bp.post("/api-keys")
def auth_create_api_key():
    """Create a new API key.
    
    Requires admin token.
    
    Body:
    - user_id: User ID
    - name: Key name/label
    - expires_in_days: Optional expiry (default: 365)
    """
    auth_error = _require_admin_mutation("CREATE_API_KEY", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    user_id = data.get("user_id")
    name = data.get("name", "API Key")
    
    try:
        expires_in_days = int(data.get("expires_in_days", "365"))
    except (ValueError, TypeError):
        expires_in_days = 365
    
    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Missing user_id"
        }), 400
    
    from copilot_core.auth.store import get_auth_store
    
    try:
        store = get_auth_store()
        result = store.create_api_key(
            user_id=user_id,
            name=name,
            expires_in_days=expires_in_days
        )
        success = True
        key = result.get("key")
        key_id = result.get("key_id")
    except Exception as e:
        _LOGGER.warning("Failed to create API key: %s", e)
        success = False
        key = None
        key_id = None
    
    return jsonify({
        "ok": success,
        "key_id": key_id,
        "key": key,
        "name": name,
        "expires_in_days": expires_in_days
    })


@auth_bp.delete("/api-keys/<key_id>")
def auth_revoke_api_key(key_id):
    """Revoke an API key.
    
    Requires admin token.
    """
    auth_error = _require_admin_mutation("REVOKE_API_KEY", "Admin token required")
    if auth_error:
        return auth_error
    
    from copilot_core.auth.store import get_auth_store
    
    try:
        store = get_auth_store()
        store.revoke_api_key(key_id=key_id)
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to revoke API key: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "key_id": key_id
    })
