from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
jax_bp = Blueprint("jax", __name__, url_prefix="/api/v1/jax")
@jax_bp.route("", methods=["GET"])
@require_token
def jax(): return jsonify({"ok": True})
