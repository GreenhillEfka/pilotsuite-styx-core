from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
hetzner2_bp = Blueprint("hetzner2", __name__, url_prefix="/api/v1/hetzner2")
@hetzner2_bp.route("", methods=["GET"])
@require_token
def hetzner2(): return jsonify({"ok": True})
