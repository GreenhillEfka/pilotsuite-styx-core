from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
goatcounter_bp = Blueprint("goatcounter", __name__, url_prefix="/api/v1/goatcounter")
@goatcounter_bp.route("", methods=["GET"])
@require_token
def goatcounter(): return jsonify({"ok": True})
