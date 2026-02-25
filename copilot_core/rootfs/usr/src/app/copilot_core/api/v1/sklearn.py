from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sklearn_bp = Blueprint("sklearn", __name__, url_prefix="/api/v1/sklearn")
@sklearn_bp.route("", methods=["GET"])
@require_token
def sklearn(): return jsonify({"ok": True})
