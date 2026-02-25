from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tutanota_bp = Blueprint("tutanota", __name__, url_prefix="/api/v1/tutanota")
@tutanota_bp.route("", methods=["GET"])
@require_token
def tutanota(): return jsonify({"ok": True})
