from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pelican_bp = Blueprint("pelican", __name__, url_prefix="/api/v1/pelican")
@pelican_bp.route("", methods=["GET"])
@require_token
def pelican(): return jsonify({"ok": True})
