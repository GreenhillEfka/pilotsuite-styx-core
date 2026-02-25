from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ifaceconfig_bp = Blueprint("ifaceconfig", __name__, url_prefix="/api/v1/ifaceconfig")
@ifaceconfig_bp.route("", methods=["GET"])
@require_token
def ifaceconfig(): return jsonify({"ok": True})
