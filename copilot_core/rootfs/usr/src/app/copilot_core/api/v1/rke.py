from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rke_bp = Blueprint("rke", __name__, url_prefix="/api/v1/rke")
@rke_bp.route("", methods=["GET"])
@require_token
def rke(): return jsonify({"ok": True})
