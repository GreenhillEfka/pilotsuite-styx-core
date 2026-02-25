from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
console_bp = Blueprint("console", __name__, url_prefix="/api/v1/console")
@console_bp.route("", methods=["GET"])
@require_token
def console(): return jsonify({"ok": True})
