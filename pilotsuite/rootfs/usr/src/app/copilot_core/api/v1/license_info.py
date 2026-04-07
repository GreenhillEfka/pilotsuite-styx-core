"""License Info API — Slice 320 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("license_info", __name__, url_prefix="/api/v1")
@bp.get("/license/status")
def get_license_status():
    return jsonify({"ok": True, "status": "active", "expires": "2026-12-31T23:59:59Z"})
@bp.get("/license/usage")
def get_license_usage():
    return jsonify({"ok": True, "used": 1, "limit": 5})
@bp.get("/license/keys")
def get_license_keys():
    return jsonify({"ok": True, "keys": []})
@bp.get("/license/features")
def get_license_features():
    return jsonify({"ok": True, "features": []})
