from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
duckdb_bp = Blueprint("duckdb", __name__, url_prefix="/api/v1/duckdb")
@duckdb_bp.route("", methods=["GET"])
@require_token
def duckdb(): return jsonify({"ok": True})
