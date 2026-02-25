from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
graphql_bp = Blueprint("graphql", __name__, url_prefix="/api/v1/graphql")
@graphql_bp.route("", methods=["GET"])
@require_token
def graphql(): return jsonify({"ok": True})
