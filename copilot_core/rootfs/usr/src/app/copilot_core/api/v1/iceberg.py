from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
iceberg_bp = Blueprint("iceberg", __name__, url_prefix="/api/v1/iceberg")
@iceberg_bp.route("", methods=["GET"])
@require_token
def iceberg(): return jsonify({"ok": True})
