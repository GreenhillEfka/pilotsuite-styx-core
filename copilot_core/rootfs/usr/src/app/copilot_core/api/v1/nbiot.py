from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nbiot_bp = Blueprint("nbiot", __name__, url_prefix="/api/v1/nbiot")
@nbiot_bp.route("", methods=["GET"])
@require_token
def nbiot(): return jsonify({"ok": True})
