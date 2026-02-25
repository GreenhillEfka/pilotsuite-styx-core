from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wifidirect_bp = Blueprint("wifidirect", __name__, url_prefix="/api/v1/wifidirect")
@wifidirect_bp.route("", methods=["GET"])
@require_token
def wifidirect(): return jsonify({"ok": True})
