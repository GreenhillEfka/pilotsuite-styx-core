from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tempo_bp = Blueprint("tempo", __name__, url_prefix="/api/v1/tempo")
@tempo_bp.route("", methods=["GET"])
@require_token
def tempo(): return jsonify({"ok": True})
