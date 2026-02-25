from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cilium_bp = Blueprint("cilium", __name__, url_prefix="/api/v1/cilium")
@cilium_bp.route("", methods=["GET"])
@require_token
def cilium(): return jsonify({"ok": True})
