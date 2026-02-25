from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
conduit_bp = Blueprint("conduit", __name__, url_prefix="/api/v1/conduit")
@conduit_bp.route("", methods=["GET"])
@require_token
def conduit(): return jsonify({"ok": True})
