from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
directx_bp = Blueprint("directx", __name__, url_prefix="/api/v1/directx")
@directx_bp.route("", methods=["GET"])
@require_token
def directx(): return jsonify({"ok": True})
