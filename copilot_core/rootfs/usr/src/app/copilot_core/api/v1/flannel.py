from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
flannel_bp = Blueprint("flannel", __name__, url_prefix="/api/v1/flannel")
@flannel_bp.route("", methods=["GET"])
@require_token
def flannel(): return jsonify({"ok": True})
