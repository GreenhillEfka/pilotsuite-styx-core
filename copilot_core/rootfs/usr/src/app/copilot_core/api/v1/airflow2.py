from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
airflow2_bp = Blueprint("airflow2", __name__, url_prefix="/api/v1/airflow2")
@airflow2_bp.route("", methods=["GET"])
@require_token
def airflow2(): return jsonify({"ok": True})
