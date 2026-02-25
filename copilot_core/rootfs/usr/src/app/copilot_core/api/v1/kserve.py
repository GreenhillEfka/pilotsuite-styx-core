from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kserve_bp = Blueprint("kserve", __name__, url_prefix="/api/v1/kserve")
@kserve_bp.route("", methods=["GET"])
@require_token
def kserve(): return jsonify({"ok": True})
