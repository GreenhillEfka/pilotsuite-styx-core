from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pxe_bp = Blueprint("pxe", __name__, url_prefix="/api/v1/pxe")
@pxe_bp.route("", methods=["GET"])
@require_token
def pxe(): return jsonify({"ok": True})
