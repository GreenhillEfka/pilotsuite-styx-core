from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rmilter_bp = Blueprint("rmilter", __name__, url_prefix="/api/v1/rmilter")
@rmilter_bp.route("", methods=["GET"])
@require_token
def rmilter(): return jsonify({"ok": True})
