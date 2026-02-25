from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
amplitude_bp = Blueprint("amplitude", __name__, url_prefix="/api/v1/amplitude")
@amplitude_bp.route("", methods=["GET"])
@require_token
def amplitude(): return jsonify({"ok": True})
