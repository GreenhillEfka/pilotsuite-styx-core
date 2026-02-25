from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
minikube_bp = Blueprint("minikube", __name__, url_prefix="/api/v1/minikube")
@minikube_bp.route("", methods=["GET"])
@require_token
def minikube(): return jsonify({"ok": True})
