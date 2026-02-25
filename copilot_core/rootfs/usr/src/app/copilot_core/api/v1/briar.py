from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
briar_bp = Blueprint("briar", __name__, url_prefix="/api/v1/briar")
@briar_bp.route("", methods=["GET"])
@require_token
def briar(): return jsonify({"ok": True})
