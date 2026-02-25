from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
catboost_bp = Blueprint("catboost", __name__, url_prefix="/api/v1/catboost")
@catboost_bp.route("", methods=["GET"])
@require_token
def catboost(): return jsonify({"ok": True})
