from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
oneapi_bp = Blueprint("oneapi", __name__, url_prefix="/api/v1/oneapi")
@oneapi_bp.route("", methods=["GET"])
@require_token
def oneapi(): return jsonify({"ok": True})
