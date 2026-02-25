from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
armadillo_bp = Blueprint("armadillo", __name__, url_prefix="/api/v1/armadillo")
@armadillo_bp.route("", methods=["GET"])
@require_token
def armadillo(): return jsonify({"ok": True})
