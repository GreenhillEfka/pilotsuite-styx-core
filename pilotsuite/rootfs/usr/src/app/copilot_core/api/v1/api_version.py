"""API Version API — Slice 333 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("api_version", __name__, url_prefix="/api/v1")
@bp.get("/api/versions")
def get_api_versions():
    return jsonify({"ok": True, "versions": ["v1"], "current": "v1"})
@bp.get("/api/deprecation")
def get_api_deprecation():
    return jsonify({"ok": True, "deprecated": [], "sunset": []})
@bp.get("/api/changelog")
def get_api_changelog():
    return jsonify({"ok": True, "changelog": []})
@bp.get("/api/compatibility")
def get_api_compatibility():
    return jsonify({"ok": True, "compatible": True})
