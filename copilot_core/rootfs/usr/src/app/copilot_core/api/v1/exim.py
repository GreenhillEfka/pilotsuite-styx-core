from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
exim_bp = Blueprint("exim", __name__, url_prefix="/api/v1/exim")
@exim_bp.route("", methods=["GET"])
@require_token
def exim(): return jsonify({"ok": True})
