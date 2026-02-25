from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ispconfig_bp = Blueprint("ispconfig", __name__, url_prefix="/api/v1/ispconfig")
@ispconfig_bp.route("", methods=["GET"])
@require_token
def ispconfig(): return jsonify({"ok": True})
