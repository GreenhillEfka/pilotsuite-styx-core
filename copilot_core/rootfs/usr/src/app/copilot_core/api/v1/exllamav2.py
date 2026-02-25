from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
exllamav2_bp = Blueprint("exllamav2", __name__, url_prefix="/api/v1/exllamav2")
@exllamav2_bp.route("", methods=["GET"])
@require_token
def exllamav2(): return jsonify({"ok": True})
