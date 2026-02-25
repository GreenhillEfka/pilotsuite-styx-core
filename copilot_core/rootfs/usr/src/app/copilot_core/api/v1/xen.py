from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
xen_bp = Blueprint("xen", __name__, url_prefix="/api/v1/xen")
@xen_bp.route("", methods=["GET"])
@require_token
def xen(): return jsonify({"ok": True})
