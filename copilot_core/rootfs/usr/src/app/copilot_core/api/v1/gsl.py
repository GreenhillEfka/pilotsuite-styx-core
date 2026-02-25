from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gsl_bp = Blueprint("gsl", __name__, url_prefix="/api/v1/gsl")
@gsl_bp.route("", methods=["GET"])
@require_token
def gsl(): return jsonify({"ok": True})
