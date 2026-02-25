from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
hudi_bp = Blueprint("hudi", __name__, url_prefix="/api/v1/hudi")
@hudi_bp.route("", methods=["GET"])
@require_token
def hudi(): return jsonify({"ok": True})
