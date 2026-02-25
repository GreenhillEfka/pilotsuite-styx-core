from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ups_bp = Blueprint("ups", __name__, url_prefix="/api/v1/ups")
@ups_bp.route("", methods=["GET"])
@require_token
def ups(): return jsonify({"ok": True})
