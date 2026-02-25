from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
clickhouse_bp = Blueprint("clickhouse", __name__, url_prefix="/api/v1/clickhouse")
@clickhouse_bp.route("", methods=["GET"])
@require_token
def clickhouse(): return jsonify({"ok": True})
