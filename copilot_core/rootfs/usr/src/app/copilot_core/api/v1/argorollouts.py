from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
argorollouts_bp = Blueprint("argorollouts", __name__, url_prefix="/api/v1/argorollouts")
@argorollouts_bp.route("", methods=["GET"])
@require_token
def argorollouts(): return jsonify({"ok": True})
