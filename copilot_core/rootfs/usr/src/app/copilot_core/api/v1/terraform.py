from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
terraform_bp = Blueprint("terraform", __name__, url_prefix="/api/v1/terraform")
@terraform_bp.route("", methods=["GET"])
@require_token
def terraform(): return jsonify({"ok": True})
