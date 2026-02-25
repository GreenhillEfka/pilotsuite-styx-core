from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
bios_bp = Blueprint("bios", __name__, url_prefix="/api/v1/bios")
@bios_bp.route("", methods=["GET"])
@require_token
def bios(): return jsonify({"ok": True})
