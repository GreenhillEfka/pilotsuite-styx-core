from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ds389_bp = Blueprint("ds389", __name__, url_prefix="/api/v1/ds389")
@ds389_bp.route("", methods=["GET"])
@require_token
def ds389(): return jsonify({"ok": True})
