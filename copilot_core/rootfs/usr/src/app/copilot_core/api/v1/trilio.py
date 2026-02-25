from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
trilio_bp = Blueprint("trilio", __name__, url_prefix="/api/v1/trilio")
@trilio_bp.route("", methods=["GET"])
@require_token
def trilio(): return jsonify({"ok": True})
