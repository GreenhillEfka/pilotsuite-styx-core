from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vultr_bp = Blueprint("vultr", __name__, url_prefix="/api/v1/vultr")
@vultr_bp.route("", methods=["GET"])
@require_token
def vultr(): return jsonify({"ok": True})
