from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
interface_bp = Blueprint("interface", __name__, url_prefix="/api/v1/interface")
@interface_bp.route("", methods=["GET"])
@require_token
def interface(): return jsonify({"ok": True})
