from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
firewall_bp = Blueprint("firewall", __name__, url_prefix="/api/v1/firewall")
@firewall_bp.route("", methods=["GET"])
@require_token
def firewall(): return jsonify({"ok": True})
