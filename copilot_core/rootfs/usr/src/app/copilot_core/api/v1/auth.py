"""Authentication setup endpoints.

Provides a setup-token endpoint for the HA integration to auto-fetch
the 1-Key-Flow token during Zero Config setup.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from copilot_core.api.security import get_auth_token, get_token_source

_LOGGER = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.get("/setup-token")
def setup_token():
    """Return the auto-generated token for initial HA integration setup.

    Only exposes the token if it was auto-generated (1-Key-Flow).
    Manually configured tokens (env/options) are never exposed — the user
    already knows them.
    """
    source = get_token_source()

    if source == "auto":
        token = get_auth_token()
        _LOGGER.info(
            "Setup token requested — returning auto-generated token (%s...%s)",
            token[:8], token[-4:],
        )
        return jsonify({"ok": True, "token": token, "source": "auto"})

    if source in ("env", "options"):
        return jsonify({
            "ok": False,
            "token": None,
            "source": source,
            "message": "Token is manually configured — retrieve it from your configuration",
        })

    return jsonify({
        "ok": False,
        "token": None,
        "source": "none",
        "message": "No token available",
    })
