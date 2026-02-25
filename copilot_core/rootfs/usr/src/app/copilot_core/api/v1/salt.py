from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
salt_bp = Blueprint("salt", __name__, url_prefix="/api/v1/salt")
@salt_bp.route("", methods=["GET"])
@require_token
def salt(): return jsonify({"ok": True})
