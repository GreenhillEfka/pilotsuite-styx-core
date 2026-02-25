from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vault_bp = Blueprint("vault", __name__, url_prefix="/api/v1/vault")
@vault_bp.route("", methods=["GET"])
@require_token
def vault(): return jsonify({"ok": True})
