from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
refind_bp = Blueprint("refind", __name__, url_prefix="/api/v1/refind")
@refind_bp.route("", methods=["GET"])
@require_token
def refind(): return jsonify({"ok": True})
