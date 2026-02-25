from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kubeadm_bp = Blueprint("kubeadm", __name__, url_prefix="/api/v1/kubeadm")
@kubeadm_bp.route("", methods=["GET"])
@require_token
def kubeadm(): return jsonify({"ok": True})
