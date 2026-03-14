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
