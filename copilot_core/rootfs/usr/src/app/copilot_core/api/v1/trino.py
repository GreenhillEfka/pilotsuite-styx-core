from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
trino_bp = Blueprint("trino", __name__, url_prefix="/api/v1/trino")
@trino_bp.route("", methods=["GET"])
@require_token
def trino(): return jsonify({"ok": True})
