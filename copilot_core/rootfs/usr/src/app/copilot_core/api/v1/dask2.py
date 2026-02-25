from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dask2_bp = Blueprint("dask2", __name__, url_prefix="/api/v1/dask2")
@dask2_bp.route("", methods=["GET"])
@require_token
def dask2(): return jsonify({"ok": True})
