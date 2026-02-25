from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
uefi_bp = Blueprint("uefi", __name__, url_prefix="/api/v1/uefi")
@uefi_bp.route("", methods=["GET"])
@require_token
def uefi(): return jsonify({"ok": True})
