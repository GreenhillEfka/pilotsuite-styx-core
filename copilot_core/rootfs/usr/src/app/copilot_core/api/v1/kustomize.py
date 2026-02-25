from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kustomize_bp = Blueprint("kustomize", __name__, url_prefix="/api/v1/kustomize")
@kustomize_bp.route("", methods=["GET"])
@require_token
def kustomize(): return jsonify({"ok": True})
