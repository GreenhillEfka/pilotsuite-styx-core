from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
impala_bp = Blueprint("impala", __name__, url_prefix="/api/v1/impala")
@impala_bp.route("", methods=["GET"])
@require_token
def impala(): return jsonify({"ok": True})
