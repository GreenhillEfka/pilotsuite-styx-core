from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pxelinux_bp = Blueprint("pxelinux", __name__, url_prefix="/api/v1/pxelinux")
@pxelinux_bp.route("", methods=["GET"])
@require_token
def pxelinux(): return jsonify({"ok": True})
