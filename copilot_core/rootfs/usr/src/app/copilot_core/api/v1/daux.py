from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
daux_bp = Blueprint("daux", __name__, url_prefix="/api/v1/daux")
@daux_bp.route("", methods=["GET"])
@require_token
def daux(): return jsonify({"ok": True})
