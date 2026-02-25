from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
elk_bp = Blueprint("elk", __name__, url_prefix="/api/v1/elk")
@elk_bp.route("", methods=["GET"])
@require_token
def elk(): return jsonify({"ok": True})
