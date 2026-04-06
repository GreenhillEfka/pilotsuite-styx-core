"""Auth API v1 - Token verification endpoint."""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from ..security import validate_token

_LOGGER = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.route("/verify", methods=["POST"])
def verify_token():
    """Verify an API token without logging failures.
    
    P2: Dedicated endpoint for clients to test token validity
    without triggering auth failure logs.
    
    Request Body:
        {"token": "your-api-token"}
        
    Response:
        {"valid": true} or {"valid": false}
    """
    try:
        data = request.get_json() or {}
        token = data.get("token", "").strip()
        
        if not token:
            return jsonify({"valid": False, "error": "Missing 'token' in request body"}), 400
            
        is_valid = validate_token(token)
        return jsonify({"valid": is_valid})
        
    except Exception as exc:
        _LOGGER.warning("Auth verify failed: %s", exc)
        return jsonify({"valid": False, "error": "Internal error"}), 500