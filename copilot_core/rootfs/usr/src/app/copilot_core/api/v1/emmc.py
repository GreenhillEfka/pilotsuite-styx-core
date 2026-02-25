from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
emmc_bp = Blueprint("emmc", __name__, url_prefix="/api/v1/emmc")
@emmc_bp.route("", methods=["GET"])
@require_token
def emmc(): return jsonify({"ok": True})
