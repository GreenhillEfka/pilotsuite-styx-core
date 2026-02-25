from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
paperspacecore_bp = Blueprint("paperspacecore", __name__, url_prefix="/api/v1/paperspacecore")
@paperspacecore_bp.route("", methods=["GET"])
@require_token
def paperspacecore(): return jsonify({"ok": True})
