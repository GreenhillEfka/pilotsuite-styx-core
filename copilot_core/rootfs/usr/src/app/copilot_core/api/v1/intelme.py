from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
intelme_bp = Blueprint("intelme", __name__, url_prefix="/api/v1/intelme")
@intelme_bp.route("", methods=["GET"])
@require_token
def intelme(): return jsonify({"ok": True})
