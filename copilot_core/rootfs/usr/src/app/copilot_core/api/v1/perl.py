from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
perl_bp = Blueprint("perl", __name__, url_prefix="/api/v1/perl")
@perl_bp.route("", methods=["GET"])
@require_token
def perl(): return jsonify({"ok": True})
