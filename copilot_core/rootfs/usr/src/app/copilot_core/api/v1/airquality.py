from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
airquality_bp = Blueprint("airquality", __name__, url_prefix="/api/v1/airquality")
@airquality_bp.route("", methods=["GET"])
@require_token
def airquality(): return jsonify({"ok": True})
