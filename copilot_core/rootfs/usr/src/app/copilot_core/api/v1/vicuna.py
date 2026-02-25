from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vicuna_bp = Blueprint("vicuna", __name__, url_prefix="/api/v1/vicuna")
@vicuna_bp.route("", methods=["GET"])
@require_token
def vicuna(): return jsonify({"ok": True})
