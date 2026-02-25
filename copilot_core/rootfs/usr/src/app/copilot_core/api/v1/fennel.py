from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fennel_bp = Blueprint("fennel", __name__, url_prefix="/api/v1/fennel")
@fennel_bp.route("", methods=["GET"])
@require_token
def fennel(): return jsonify({"ok": True})
