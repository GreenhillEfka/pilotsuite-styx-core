from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kopano_bp = Blueprint("kopano", __name__, url_prefix="/api/v1/kopano")
@kopano_bp.route("", methods=["GET"])
@require_token
def kopano(): return jsonify({"ok": True})
