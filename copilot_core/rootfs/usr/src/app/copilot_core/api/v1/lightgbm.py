from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
lightgbm_bp = Blueprint("lightgbm", __name__, url_prefix="/api/v1/lightgbm")
@lightgbm_bp.route("", methods=["GET"])
@require_token
def lightgbm(): return jsonify({"ok": True})
