from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mistral_bp = Blueprint("mistral", __name__, url_prefix="/api/v1/mistral")
@mistral_bp.route("", methods=["GET"])
@require_token
def mistral(): return jsonify({"ok": True})
