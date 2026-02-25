from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
binary_bp = Blueprint("binary", __name__, url_prefix="/api/v1/binary_sensor")
@binary_bp.route("", methods=["GET"])
@require_token
def binary(): return jsonify({"ok": True})
