from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
airflow_bp = Blueprint("airflow", __name__, url_prefix="/api/v1/airflow")
@airflow_bp.route("", methods=["GET"])
@require_token
def airflow(): return jsonify({"ok": True})
