from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
copier_bp = Blueprint("copier", __name__, url_prefix="/api/v1/copier")
@copier_bp.route("", methods=["GET"])
@require_token
def copier(): return jsonify({"ok": True})
