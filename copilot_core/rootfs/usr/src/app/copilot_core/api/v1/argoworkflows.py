from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
argoworkflows_bp = Blueprint("argoworkflows", __name__, url_prefix="/api/v1/argoworkflows")
@argoworkflows_bp.route("", methods=["GET"])
@require_token
def argoworkflows(): return jsonify({"ok": True})
