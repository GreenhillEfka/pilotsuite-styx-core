from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
grpc_bp = Blueprint("grpc", __name__, url_prefix="/api/v1/grpc")
@grpc_bp.route("", methods=["GET"])
@require_token
def grpc(): return jsonify({"ok": True})
