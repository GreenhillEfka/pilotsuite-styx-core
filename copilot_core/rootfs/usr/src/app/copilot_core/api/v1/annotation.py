"""Annotation API — Slice 345 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("annotation", __name__, url_prefix="/api/v1")
@bp.get("/annotations/list")
def get_annotations_list():
    return jsonify({"ok": True, "annotations": []})
@bp.post("/annotations/create")
def create_annotation():
    data = request.get_json() or {}
    return jsonify({"ok": True, "id": data.get("text")})
@bp.delete("/annotations/delete")
def delete_annotation():
    data = request.get_json() or {}
    return jsonify({"ok": True, "deleted": data.get("id")})
@bp.get("/annotations/search")
def search_annotations():
    return jsonify({"ok": True, "results": []})
