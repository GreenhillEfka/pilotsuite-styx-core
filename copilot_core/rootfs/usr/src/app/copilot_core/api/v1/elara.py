from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
elara_bp = Blueprint("elara", __name__, url_prefix="/api/v1/elara")
@elara_bp.route("", methods=["GET"])
@require_token
def elara(): return jsonify({"ok": True})
