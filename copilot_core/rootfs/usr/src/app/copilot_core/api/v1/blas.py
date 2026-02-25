from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
blas_bp = Blueprint("blas", __name__, url_prefix="/api/v1/blas")
@blas_bp.route("", methods=["GET"])
@require_token
def blas(): return jsonify({"ok": True})
