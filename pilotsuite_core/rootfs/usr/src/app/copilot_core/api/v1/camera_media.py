"""Camera & Media API — Slice 244 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("camera_media", __name__, url_prefix="/api/v1")
@bp.get("/camera/stream")
def get_camera_stream():
    return jsonify({"ok": True, "stream_url": "rtsp://localhost:8554/stream"})
@bp.get("/media/list")
def list_media():
    return jsonify({"ok": True, "media": []})
@bp.post("/media/upload")
def upload_media():
    data = request.get_json() or {}
    return jsonify({"ok": True, "media_id": data.get("id")})
