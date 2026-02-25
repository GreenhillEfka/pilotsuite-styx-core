from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dask_bp = Blueprint("dask", __name__, url_prefix="/api/v1/dask")
@dask_bp.route("", methods=["GET"])
@require_token
def dask(): return jsonify({"ok": True})
