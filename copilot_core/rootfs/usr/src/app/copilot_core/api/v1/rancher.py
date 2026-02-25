from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rancher_bp = Blueprint("rancher", __name__, url_prefix="/api/v1/rancher")
@rancher_bp.route("", methods=["GET"])
@require_token
def rancher(): return jsonify({"ok": True})
