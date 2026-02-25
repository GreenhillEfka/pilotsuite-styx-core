from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
plesk_bp = Blueprint("plesk", __name__, url_prefix="/api/v1/plesk")
@plesk_bp.route("", methods=["GET"])
@require_token
def plesk(): return jsonify({"ok": True})
