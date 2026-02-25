from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
qemu_bp = Blueprint("qemu", __name__, url_prefix="/api/v1/qemu")
@qemu_bp.route("", methods=["GET"])
@require_token
def qemu(): return jsonify({"ok": True})
