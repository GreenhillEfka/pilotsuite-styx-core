"""Dependency Info API — Slice 331 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("dependency_info", __name__, url_prefix="/api/v1")
@bp.get("/dependencies/list")
def get_dependencies_list():
    return jsonify({"ok": True, "dependencies": []})
@bp.get("/dependencies/status")
def get_dependencies_status():
    return jsonify({"ok": True, "satisfied": 0, "missing": 0})
@bp.get("/dependencies/graph")
def get_dependencies_graph():
    return jsonify({"ok": True, "graph": {}})
@bp.get("/dependencies/cycles")
def get_dependencies_cycles():
    return jsonify({"ok": True, "cycles": []})
