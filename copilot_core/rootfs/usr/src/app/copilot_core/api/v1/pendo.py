from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pendo_bp = Blueprint("pendo", __name__, url_prefix="/api/v1/pendo")
@pendo_bp.route("", methods=["GET"])
@require_token
def pendo(): return jsonify({"ok": True})
