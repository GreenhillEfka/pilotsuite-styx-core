from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
virtualizor_bp = Blueprint("virtualizor", __name__, url_prefix="/api/v1/virtualizor")
@virtualizor_bp.route("", methods=["GET"])
@require_token
def virtualizor(): return jsonify({"ok": True})
