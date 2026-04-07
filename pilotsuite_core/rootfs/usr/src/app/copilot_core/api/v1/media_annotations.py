"""Media & Annotations API — Slice 215."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("media_annotations", __name__, url_prefix="/api/v1")
@bp.get("/media/albums")
def get_media_albums():
    return jsonify({"ok": True, "albums": []})
@bp.get("/annotations/layers")
def get_annotations_layers():
    return jsonify({"ok": True, "layers": []})
@bp.post("/annotations/create")
def create_annotation():
    data = request.get_json() or {}
    return jsonify({"ok": True, "annotation": data})
