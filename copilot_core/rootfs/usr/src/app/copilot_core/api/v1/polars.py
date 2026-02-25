from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
polars_bp = Blueprint("polars", __name__, url_prefix="/api/v1/polars")
@polars_bp.route("", methods=["GET"])
@require_token
def polars(): return jsonify({"ok": True})
