"""Version API for PilotSuite Core."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token
from copilot_core.versioning import get_runtime_version

version_bp = Blueprint("version", __name__, url_prefix="/api/v1/version")


@version_bp.before_request
def _require_auth():
    if not validate_token(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401


@version_bp.get("")
def get_version():
    return jsonify(
        {
            "ok": True,
            "version": get_runtime_version(),
            "api_version": "v1",
        }
    )


__all__ = ["version_bp"]
