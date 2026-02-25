from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
applehome_bp = Blueprint("applehome", __name__, url_prefix="/api/v1/applehome")
@applehome_bp.route("", methods=["GET"])
@require_token
def applehome(): return jsonify({"ok": True})
