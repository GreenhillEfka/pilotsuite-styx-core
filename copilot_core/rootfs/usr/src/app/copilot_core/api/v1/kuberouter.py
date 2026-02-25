from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kuberouter_bp = Blueprint("kuberouter", __name__, url_prefix="/api/v1/kuberouter")
@kuberouter_bp.route("", methods=["GET"])
@require_token
def kuberouter(): return jsonify({"ok": True})
