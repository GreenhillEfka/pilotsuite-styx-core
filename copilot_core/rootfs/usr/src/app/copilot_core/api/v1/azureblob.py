from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
azureblob_bp = Blueprint("azureblob", __name__, url_prefix="/api/v1/azureblob")
@azureblob_bp.route("", methods=["GET"])
@require_token
def azureblob(): return jsonify({"ok": True})
