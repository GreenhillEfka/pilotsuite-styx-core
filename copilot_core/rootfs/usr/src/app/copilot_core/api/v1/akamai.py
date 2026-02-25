from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
akamai_bp = Blueprint("akamai", __name__, url_prefix="/api/v1/akamai")
@akamai_bp.route("", methods=["GET"])
@require_token
def akamai(): return jsonify({"ok": True})
