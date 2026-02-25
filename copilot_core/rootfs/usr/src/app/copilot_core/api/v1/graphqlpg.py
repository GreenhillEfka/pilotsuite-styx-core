from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
graphqlpg_bp = Blueprint("graphqlpg", __name__, url_prefix="/api/v1/graphqlpg")
@graphqlpg_bp.route("", methods=["GET"])
@require_token
def graphqlpg(): return jsonify({"ok": True})
