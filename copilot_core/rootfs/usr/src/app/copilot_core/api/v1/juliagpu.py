from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
juliagpu_bp = Blueprint("juliagpu", __name__, url_prefix="/api/v1/juliagpu")
@juliagpu_bp.route("", methods=["GET"])
@require_token
def juliagpu(): return jsonify({"ok": True})
