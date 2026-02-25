from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fathom_bp = Blueprint("fathom", __name__, url_prefix="/api/v1/fathom")
@fathom_bp.route("", methods=["GET"])
@require_token
def fathom(): return jsonify({"ok": True})
