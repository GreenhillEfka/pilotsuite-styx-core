from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
erlang_bp = Blueprint("erlang", __name__, url_prefix="/api/v1/erlang")
@erlang_bp.route("", methods=["GET"])
@require_token
def erlang(): return jsonify({"ok": True})
