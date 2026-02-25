from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dendrite_bp = Blueprint("dendrite", __name__, url_prefix="/api/v1/dendrite")
@dendrite_bp.route("", methods=["GET"])
@require_token
def dendrite(): return jsonify({"ok": True})
