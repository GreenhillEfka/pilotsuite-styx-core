from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
todo_bp = Blueprint("todo", __name__, url_prefix="/api/v1/todo")
@todo_bp.route("", methods=["GET"])
@require_token
def todo(): return jsonify({"ok": True})
