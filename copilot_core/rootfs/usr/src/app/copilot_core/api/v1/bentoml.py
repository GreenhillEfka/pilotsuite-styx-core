from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
bentoml_bp = Blueprint("bentoml", __name__, url_prefix="/api/v1/bentoml")
@bentoml_bp.route("", methods=["GET"])
@require_token
def bentoml(): return jsonify({"ok": True})
