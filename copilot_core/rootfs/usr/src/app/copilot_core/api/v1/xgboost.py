from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
xgboost_bp = Blueprint("xgboost", __name__, url_prefix="/api/v1/xgboost")
@xgboost_bp.route("", methods=["GET"])
@require_token
def xgboost(): return jsonify({"ok": True})
