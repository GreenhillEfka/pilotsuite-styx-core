from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
secboot_bp = Blueprint("secboot", __name__, url_prefix="/api/v1/secboot")
@secboot_bp.route("", methods=["GET"])
@require_token
def secboot(): return jsonify({"ok": True})
