from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
csharp_bp = Blueprint("csharp", __name__, url_prefix="/api/v1/csharp")
@csharp_bp.route("", methods=["GET"])
@require_token
def csharp(): return jsonify({"ok": True})
