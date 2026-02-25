from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dkim_bp = Blueprint("dkim", __name__, url_prefix="/api/v1/dkim")
@dkim_bp.route("", methods=["GET"])
@require_token
def dkim(): return jsonify({"ok": True})
