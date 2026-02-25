from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
alexa_bp = Blueprint("alexa", __name__, url_prefix="/api/v1/alexa")
@alexa_bp.route("", methods=["GET"])
@require_token
def alexa(): return jsonify({"ok": True})
