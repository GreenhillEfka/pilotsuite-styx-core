from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
segment_bp = Blueprint("segment", __name__, url_prefix="/api/v1/segment")
@segment_bp.route("", methods=["GET"])
@require_token
def segment(): return jsonify({"ok": True})
