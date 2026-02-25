from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fftw_bp = Blueprint("fftw", __name__, url_prefix="/api/v1/fftw")
@fftw_bp.route("", methods=["GET"])
@require_token
def fftw(): return jsonify({"ok": True})
