from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fullstory_bp = Blueprint("fullstory", __name__, url_prefix="/api/v1/fullstory")
@fullstory_bp.route("", methods=["GET"])
@require_token
def fullstory(): return jsonify({"ok": True})
