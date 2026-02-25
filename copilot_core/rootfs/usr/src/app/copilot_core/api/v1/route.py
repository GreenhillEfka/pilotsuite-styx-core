from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
route_bp = Blueprint("route", __name__, url_prefix="/api/v1/route")
@route_bp.route("", methods=["GET"])
@require_token
def route(): return jsonify({"ok": True})
