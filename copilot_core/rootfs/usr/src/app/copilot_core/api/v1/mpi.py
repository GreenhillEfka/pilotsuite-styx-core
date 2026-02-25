from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mpi_bp = Blueprint("mpi", __name__, url_prefix="/api/v1/mpi")
@mpi_bp.route("", methods=["GET"])
@require_token
def mpi(): return jsonify({"ok": True})
