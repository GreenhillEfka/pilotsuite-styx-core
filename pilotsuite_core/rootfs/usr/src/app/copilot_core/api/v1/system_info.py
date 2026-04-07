"""System Info API — Slice 315 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("system_info", __name__, url_prefix="/api/v1")
@bp.get("/system/info")
def get_system_info():
    return jsonify({"ok": True, "os": "Linux", "arch": "x64", "version": "15.3.40"})
@bp.get("/system/uptime")
def get_system_uptime():
    return jsonify({"ok": True, "uptime": 3600})
@bp.get("/system/load")
def get_system_load():
    return jsonify({"ok": True, "load": 0.5})
@bp.get("/system/memory")
def get_system_memory():
    return jsonify({"ok": True, "memory": "128MB"})
