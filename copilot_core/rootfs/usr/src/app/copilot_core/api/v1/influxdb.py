from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
influxdb_bp = Blueprint("influxdb", __name__, url_prefix="/api/v1/influxdb")
@influxdb_bp.route("", methods=["GET"])
@require_token
def influxdb(): return jsonify({"ok": True})
