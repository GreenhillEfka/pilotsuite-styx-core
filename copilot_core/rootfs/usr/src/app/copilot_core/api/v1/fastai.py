from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fastai_bp = Blueprint("fastai", __name__, url_prefix="/api/v1/fastai")
@fastai_bp.route("", methods=["GET"])
@require_token
def fastai(): return jsonify({"ok": True})
