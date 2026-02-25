from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
openblas_bp = Blueprint("openblas", __name__, url_prefix="/api/v1/openblas")
@openblas_bp.route("", methods=["GET"])
@require_token
def openblas(): return jsonify({"ok": True})
