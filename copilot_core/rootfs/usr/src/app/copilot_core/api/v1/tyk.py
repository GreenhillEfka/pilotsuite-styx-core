from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tyk_bp = Blueprint("tyk", __name__, url_prefix="/api/v1/tyk")
@tyk_bp.route("", methods=["GET"])
@require_token
def tyk(): return jsonify({"ok": True})
