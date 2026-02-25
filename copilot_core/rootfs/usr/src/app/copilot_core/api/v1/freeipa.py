from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
freeipa_bp = Blueprint("freeipa", __name__, url_prefix="/api/v1/freeipa")
@freeipa_bp.route("", methods=["GET"])
@require_token
def freeipa(): return jsonify({"ok": True})
