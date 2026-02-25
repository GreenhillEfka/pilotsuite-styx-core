from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
python_bp = Blueprint("python", __name__, url_prefix="/api/v1/python")
@python_bp.route("", methods=["GET"])
@require_token
def python(): return jsonify({"ok": True})
