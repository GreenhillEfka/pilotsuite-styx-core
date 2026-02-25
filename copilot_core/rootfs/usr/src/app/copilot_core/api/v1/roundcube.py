from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
roundcube_bp = Blueprint("roundcube", __name__, url_prefix="/api/v1/roundcube")
@roundcube_bp.route("", methods=["GET"])
@require_token
def roundcube(): return jsonify({"ok": True})
