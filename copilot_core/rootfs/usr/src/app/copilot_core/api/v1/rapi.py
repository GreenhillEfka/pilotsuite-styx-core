from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rapi_bp = Blueprint("rapi", __name__, url_prefix="/api/v1/rapi")
@rapi_bp.route("", methods=["GET"])
@require_token
def rapi(): return jsonify({"ok": True})
