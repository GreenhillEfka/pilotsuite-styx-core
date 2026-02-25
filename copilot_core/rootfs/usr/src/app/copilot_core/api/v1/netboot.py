from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
netboot_bp = Blueprint("netboot", __name__, url_prefix="/api/v1/netboot")
@netboot_bp.route("", methods=["GET"])
@require_token
def netboot(): return jsonify({"ok": True})
