from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
elixir_bp = Blueprint("elixir", __name__, url_prefix="/api/v1/elixir")
@elixir_bp.route("", methods=["GET"])
@require_token
def elixir(): return jsonify({"ok": True})
