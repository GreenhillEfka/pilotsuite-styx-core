from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
digitalocean_bp = Blueprint("digitalocean", __name__, url_prefix="/api/v1/digitalocean")
@digitalocean_bp.route("", methods=["GET"])
@require_token
def digitalocean(): return jsonify({"ok": True})
