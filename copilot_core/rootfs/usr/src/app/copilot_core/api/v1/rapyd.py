from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rapyd_bp = Blueprint("rapyd", __name__, url_prefix="/api/v1/rapyd")
@rapyd_bp.route("", methods=["GET"])
@require_token
def rapyd(): return jsonify({"ok": True})
