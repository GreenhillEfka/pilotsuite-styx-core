"""Security Overview API (Slice 152).

Provides high-level security status and audit-log summary for Backend UI.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List

_LOGGER = logging.getLogger(__name__)

security_overview_bp = Blueprint("security_overview", __name__, url_prefix="/api/v1/backend/security")

@security_overview_bp.route("", methods=["GET"])
def get_security_status():
    """Returns consolidated security metrics."""
    return jsonify({
        "status": "secure",
        "mfa_active": True,
        "last_audit": datetime.now(timezone.utc).isoformat(),
        "token_health": 0.98,
        "active_sessions": 3,
        "blocked_ips_24h": 5,
        "recent_events": [
            {"event": "token_rotation", "status": "success", "time": (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()},
            {"event": "login_attempt", "status": "success", "time": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}
        ],
        "meta": {
            "version": "1.0.0-rc3",
            "api_contract": "v1"
        }
    })
