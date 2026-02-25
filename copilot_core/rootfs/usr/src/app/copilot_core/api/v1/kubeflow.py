from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kubeflow_bp = Blueprint("kubeflow", __name__, url_prefix="/api/v1/kubeflow")
@kubeflow_bp.route("", methods=["GET"])
@require_token
def kubeflow(): return jsonify({"ok": True})
