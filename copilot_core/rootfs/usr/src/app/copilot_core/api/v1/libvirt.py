from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
libvirt_bp = Blueprint("libvirt", __name__, url_prefix="/api/v1/libvirt")
@libvirt_bp.route("", methods=["GET"])
@require_token
def libvirt(): return jsonify({"ok": True})
