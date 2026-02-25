from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
hugo_bp = Blueprint("hugo", __name__, url_prefix="/api/v1/hugo")
@hugo_bp.route("", methods=["GET"])
@require_token
def hugo(): return jsonify({"ok": True})
