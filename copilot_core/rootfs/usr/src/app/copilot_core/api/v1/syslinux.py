from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
syslinux_bp = Blueprint("syslinux", __name__, url_prefix="/api/v1/syslinux")
@syslinux_bp.route("", methods=["GET"])
@require_token
def syslinux(): return jsonify({"ok": True})
