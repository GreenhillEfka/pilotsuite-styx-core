from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
docute_bp = Blueprint("docute", __name__, url_prefix="/api/v1/docute")
@docute_bp.route("", methods=["GET"])
@require_token
def docute(): return jsonify({"ok": True})
