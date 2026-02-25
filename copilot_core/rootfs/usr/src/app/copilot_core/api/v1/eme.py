from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
eme_bp = Blueprint("eme", __name__, url_prefix="/api/v1/eme")
@eme_bp.route("", methods=["GET"])
@require_token
def eme(): return jsonify({"ok": True})
