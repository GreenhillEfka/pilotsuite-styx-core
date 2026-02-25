from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
froxlor_bp = Blueprint("froxlor", __name__, url_prefix="/api/v1/froxlor")
@froxlor_bp.route("", methods=["GET"])
@require_token
def froxlor(): return jsonify({"ok": True})
