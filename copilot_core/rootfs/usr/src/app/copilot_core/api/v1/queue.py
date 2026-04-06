"""Queue API — Slice 419 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("queue", __name__, url_prefix="/api/v1")
@bp.get("/queues/list")
def get_queues_list():
    return jsonify({"ok": True, "queues": []})
@bp.get("/queues/size")
def get_queue_size():
    return jsonify({"ok": True, "size": 0})
