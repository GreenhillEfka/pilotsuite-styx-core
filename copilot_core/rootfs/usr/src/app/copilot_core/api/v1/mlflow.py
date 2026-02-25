from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mlflow_bp = Blueprint("mlflow", __name__, url_prefix="/api/v1/mlflow")
@mlflow_bp.route("", methods=["GET"])
@require_token
def mlflow(): return jsonify({"ok": True})
