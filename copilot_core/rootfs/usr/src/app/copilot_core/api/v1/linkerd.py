from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
linkerd_bp = Blueprint("linkerd", __name__, url_prefix="/api/v1/linkerd")
@linkerd_bp.route("", methods=["GET"])
@require_token
def linkerd(): return jsonify({"ok": True})
