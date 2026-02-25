from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cloudinit_bp = Blueprint("cloudinit", __name__, url_prefix="/api/v1/cloudinit")
@cloudinit_bp.route("", methods=["GET"])
@require_token
def cloudinit(): return jsonify({"ok": True})
