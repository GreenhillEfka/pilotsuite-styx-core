from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sveltekit_bp = Blueprint("sveltekit", __name__, url_prefix="/api/v1/sveltekit")
@sveltekit_bp.route("", methods=["GET"])
@require_token
def sveltekit(): return jsonify({"ok": True})
