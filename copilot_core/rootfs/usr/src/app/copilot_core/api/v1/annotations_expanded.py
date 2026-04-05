"""Annotations API Expansion — Slice 207."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("annotations_expanded", __name__, url_prefix="/api/v1/annotations")

@bp.get("/entity/<entity_id>")
def get_entity_annotations(entity_id: str):
    """Get annotations for an entity."""
    return jsonify({"ok": True, "entity_id": entity_id, "annotations": []})

@bp.post("/entity/<entity_id>")
def add_entity_annotation(entity_id: str):
    """Add annotation to an entity."""
    data = request.get_json() or {}
    return jsonify({"ok": True, "entity_id": entity_id, "annotation": data, "created": datetime.now(timezone.utc).isoformat()})

@bp.delete("/entity/<entity_id>/<annotation_id>")
def delete_entity_annotation(entity_id: str, annotation_id: str):
    """Delete annotation from entity."""
    return jsonify({"ok": True, "deleted": annotation_id})

@bp.get("/layers")
def get_annotation_layers():
    """Get all annotation layers."""
    return jsonify({"ok": True, "layers": []})
