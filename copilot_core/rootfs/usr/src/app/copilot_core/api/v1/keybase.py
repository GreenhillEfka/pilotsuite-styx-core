from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
keybase_bp = Blueprint("keybase", __name__, url_prefix="/api/v1/keybase")
@keybase_bp.route("", methods=["GET"])
@require_token
def keybase(): return jsonify({"ok": True})
