from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
foreman_bp = Blueprint("foreman", __name__, url_prefix="/api/v1/foreman")
@foreman_bp.route("", methods=["GET"])
@require_token
def foreman(): return jsonify({"ok": True})
