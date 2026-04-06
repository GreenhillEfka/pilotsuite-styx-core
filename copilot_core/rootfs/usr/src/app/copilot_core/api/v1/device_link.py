"""Device Link API — Slice 511 (CORE ONLY).
Symbiotic entity linking HA devices to Core.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("device_link", __name__, url_prefix="/api/v1")

@bp.get("/devices/links")
def list_device_links():
    return jsonify({"ok": True, "links": []})

@bp.post("/devices/links")
def create_device_link():
    data = request.get_json() or {}
    return jsonify({"ok": True, "link_id": data.get("ha_entity_id")})

@bp.get("/devices/links/<link_id>/capabilities")
def get_device_capabilities(link_id):
    return jsonify({"ok": True, "link_id": link_id, "capabilities": []})
