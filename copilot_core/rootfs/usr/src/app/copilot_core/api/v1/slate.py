from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
slate_bp = Blueprint("slate", __name__, url_prefix="/api/v1/slate")
@slate_bp.route("", methods=["GET"])
@require_token
def slate(): return jsonify({"ok": True})
