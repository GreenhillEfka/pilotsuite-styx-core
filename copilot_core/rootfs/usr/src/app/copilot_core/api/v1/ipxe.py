from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ipxe_bp = Blueprint("ipxe", __name__, url_prefix="/api/v1/ipxe")
@ipxe_bp.route("", methods=["GET"])
@require_token
def ipxe(): return jsonify({"ok": True})
