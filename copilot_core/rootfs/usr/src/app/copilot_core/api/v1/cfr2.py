from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cfr2_bp = Blueprint("cfr2", __name__, url_prefix="/api/v1/cfr2")
@cfr2_bp.route("", methods=["GET"])
@require_token
def cfr2(): return jsonify({"ok": True})
