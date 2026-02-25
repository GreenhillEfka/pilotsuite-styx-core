from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
virtink_bp = Blueprint("virtink", __name__, url_prefix="/api/v1/virtink")
@virtink_bp.route("", methods=["GET"])
@require_token
def virtink(): return jsonify({"ok": True})
