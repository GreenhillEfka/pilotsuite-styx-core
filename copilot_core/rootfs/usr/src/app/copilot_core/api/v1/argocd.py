from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
argocd_bp = Blueprint("argocd", __name__, url_prefix="/api/v1/argocd")
@argocd_bp.route("", methods=["GET"])
@require_token
def argocd(): return jsonify({"ok": True})
