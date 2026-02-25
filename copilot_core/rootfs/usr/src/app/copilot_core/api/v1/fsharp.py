from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fsharp_bp = Blueprint("fsharp", __name__, url_prefix="/api/v1/fsharp")
@fsharp_bp.route("", methods=["GET"])
@require_token
def fsharp(): return jsonify({"ok": True})
