from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
railway_bp = Blueprint("railway", __name__, url_prefix="/api/v1/railway")
@railway_bp.route("", methods=["GET"])
@require_token
def railway(): return jsonify({"ok": True})
