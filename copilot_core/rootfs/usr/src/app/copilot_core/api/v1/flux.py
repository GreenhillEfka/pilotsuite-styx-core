from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
flux_bp = Blueprint("flux", __name__, url_prefix="/api/v1/flux")
@flux_bp.route("", methods=["GET"])
@require_token
def flux(): return jsonify({"ok": True})
