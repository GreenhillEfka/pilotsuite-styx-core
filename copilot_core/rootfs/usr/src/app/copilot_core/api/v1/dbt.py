from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dbt_bp = Blueprint("dbt", __name__, url_prefix="/api/v1/dbt")
@dbt_bp.route("", methods=["GET"])
@require_token
def dbt(): return jsonify({"ok": True})
