from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
scheme_bp = Blueprint("scheme", __name__, url_prefix="/api/v1/scheme")
@scheme_bp.route("", methods=["GET"])
@require_token
def scheme(): return jsonify({"ok": True})
