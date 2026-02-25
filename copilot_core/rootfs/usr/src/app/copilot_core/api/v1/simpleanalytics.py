from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
simpleanalytics_bp = Blueprint("simpleanalytics", __name__, url_prefix="/api/v1/simpleanalytics")
@simpleanalytics_bp.route("", methods=["GET"])
@require_token
def simpleanalytics(): return jsonify({"ok": True})
