from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
trl_bp = Blueprint("trl", __name__, url_prefix="/api/v1/trl")
@trl_bp.route("", methods=["GET"])
@require_token
def trl(): return jsonify({"ok": True})
