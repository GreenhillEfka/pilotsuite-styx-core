from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
haskell_bp = Blueprint("haskell", __name__, url_prefix="/api/v1/haskell")
@haskell_bp.route("", methods=["GET"])
@require_token
def haskell(): return jsonify({"ok": True})
