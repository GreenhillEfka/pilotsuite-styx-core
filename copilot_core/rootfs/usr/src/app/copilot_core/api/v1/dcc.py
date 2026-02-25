from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dcc_bp = Blueprint("dcc", __name__, url_prefix="/api/v1/dcc")
@dcc_bp.route("", methods=["GET"])
@require_token
def dcc(): return jsonify({"ok": True})
