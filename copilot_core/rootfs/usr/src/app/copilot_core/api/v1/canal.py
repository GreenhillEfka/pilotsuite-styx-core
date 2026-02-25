from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
canal_bp = Blueprint("canal", __name__, url_prefix="/api/v1/canal")
@canal_bp.route("", methods=["GET"])
@require_token
def canal(): return jsonify({"ok": True})
