from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pixelfed_bp = Blueprint("pixelfed", __name__, url_prefix="/api/v1/pixelfed")
@pixelfed_bp.route("", methods=["GET"])
@require_token
def pixelfed(): return jsonify({"ok": True})
