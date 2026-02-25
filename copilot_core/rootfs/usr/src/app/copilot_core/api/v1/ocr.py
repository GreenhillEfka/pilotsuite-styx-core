from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ocr_bp = Blueprint("ocr", __name__, url_prefix="/api/v1/ocr")
@ocr_bp.route("", methods=["GET"])
@require_token
def ocr(): return jsonify({"ok": True})
