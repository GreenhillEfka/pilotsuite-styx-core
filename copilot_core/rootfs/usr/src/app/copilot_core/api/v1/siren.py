from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
siren_bp = Blueprint("siren", __name__, url_prefix="/api/v1/siren")
@siren_bp.route("", methods=["GET"])
@require_token
def siren(): return jsonify({"ok": True})
