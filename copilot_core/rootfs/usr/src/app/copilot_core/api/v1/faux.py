from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
faux_bp = Blueprint("faux", __name__, url_prefix="/api/v1/faux")
@faux_bp.route("", methods=["GET"])
@require_token
def faux(): return jsonify({"ok": True})
