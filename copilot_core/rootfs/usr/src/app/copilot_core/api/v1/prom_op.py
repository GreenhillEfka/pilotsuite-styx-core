from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
prom_op_bp = Blueprint("prom_op", __name__, url_prefix="/api/v1/prom_op")
@prom_op_bp.route("", methods=["GET"])
@require_token
def prom_op(): return jsonify({"ok": True})
