from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
isdn_bp = Blueprint("isdn", __name__, url_prefix="/api/v1/isdn")
@isdn_bp.route("", methods=["GET"])
@require_token
def isdn(): return jsonify({"ok": True})
