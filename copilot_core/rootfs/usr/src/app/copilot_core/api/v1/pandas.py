from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pandas_bp = Blueprint("pandas", __name__, url_prefix="/api/v1/pandas")
@pandas_bp.route("", methods=["GET"])
@require_token
def pandas(): return jsonify({"ok": True})
