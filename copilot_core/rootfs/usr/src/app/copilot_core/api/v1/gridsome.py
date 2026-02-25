from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gridsome_bp = Blueprint("gridsome", __name__, url_prefix="/api/v1/gridsome")
@gridsome_bp.route("", methods=["GET"])
@require_token
def gridsome(): return jsonify({"ok": True})
