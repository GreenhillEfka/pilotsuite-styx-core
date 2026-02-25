from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
spark_bp = Blueprint("spark", __name__, url_prefix="/api/v1/spark")
@spark_bp.route("", methods=["GET"])
@require_token
def spark(): return jsonify({"ok": True})
