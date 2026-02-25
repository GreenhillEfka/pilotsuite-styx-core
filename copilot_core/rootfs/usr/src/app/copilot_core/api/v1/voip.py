from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
voip_bp = Blueprint("voip", __name__, url_prefix="/api/v1/voip")
@voip_bp.route("", methods=["GET"])
@require_token
def voip(): return jsonify({"ok": True})
