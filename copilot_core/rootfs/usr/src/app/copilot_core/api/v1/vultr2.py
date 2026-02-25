from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vultr2_bp = Blueprint("vultr2", __name__, url_prefix="/api/v1/vultr2")
@vultr2_bp.route("", methods=["GET"])
@require_token
def vultr2(): return jsonify({"ok": True})
