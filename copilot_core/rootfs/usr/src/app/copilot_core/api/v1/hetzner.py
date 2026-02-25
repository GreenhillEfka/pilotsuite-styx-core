from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
hetzner_bp = Blueprint("hetzner", __name__, url_prefix="/api/v1/hetzner")
@hetzner_bp.route("", methods=["GET"])
@require_token
def hetzner(): return jsonify({"ok": True})
