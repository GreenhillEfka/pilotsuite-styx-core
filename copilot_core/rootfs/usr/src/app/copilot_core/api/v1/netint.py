from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
netint_bp = Blueprint("netint", __name__, url_prefix="/api/v1/netint")
@netint_bp.route("", methods=["GET"])
@require_token
def netint(): return jsonify({"ok": True})
