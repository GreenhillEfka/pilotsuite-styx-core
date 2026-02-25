from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gamma_bp = Blueprint("gamma", __name__, url_prefix="/api/v1/gamma")
@gamma_bp.route("", methods=["GET"])
@require_token
def gamma(): return jsonify({"ok": True})
