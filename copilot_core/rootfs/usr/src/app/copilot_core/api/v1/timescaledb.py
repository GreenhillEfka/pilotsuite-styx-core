from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
timescaledb_bp = Blueprint("timescaledb", __name__, url_prefix="/api/v1/timescaledb")
@timescaledb_bp.route("", methods=["GET"])
@require_token
def timescaledb(): return jsonify({"ok": True})
