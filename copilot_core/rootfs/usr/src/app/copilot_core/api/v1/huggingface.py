from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
huggingface_bp = Blueprint("huggingface", __name__, url_prefix="/api/v1/huggingface")
@huggingface_bp.route("", methods=["GET"])
@require_token
def huggingface(): return jsonify({"ok": True})
