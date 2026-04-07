"""SOTA Backend UI Wrapper (Slice 145).

Standardized response wrapper for all Backend UI endpoints.
Format: { ok, tab, generated_at, data, meta{cache_ttl_s, trace_id, version} }
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional

from flask import Blueprint, jsonify, request, Response

_LOGGER = logging.getLogger(__name__)

backend_ui_wrapper_bp = Blueprint("backend_ui_wrapper", __name__, url_prefix="/api/v1/backend_ui")

# Version incremented on each API change
API_VERSION = "1.0.0-rc2"


def wrap_response(tab: str, cache_ttl_s: Optional[int] = None):
    """Decorator to wrap endpoint responses in standardized format."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            trace_id = str(uuid.uuid4())[:8]
            generated_at = datetime.now(timezone.utc).isoformat()
            
            try:
                result = f(*args, **kwargs)
                
                # Handle tuple responses (data, status_code)
                if isinstance(result, tuple):
                    data, status_code = result
                else:
                    data, status_code = result, 200
                
                # If already a Response, return as-is
                if isinstance(data, Response):
                    return data
                
                wrapped = {
                    "ok": status_code < 400,
                    "tab": tab,
                    "generated_at": generated_at,
                    "data": data if status_code < 400 else None,
                    "error": data if status_code >= 400 else None,
                    "meta": {
                        "cache_ttl_s": cache_ttl_s,
                        "trace_id": trace_id,
                        "version": API_VERSION,
                    }
                }
                
                return jsonify(wrapped), status_code
                
            except Exception as exc:
                _LOGGER.error("Error in %s endpoint: %s", tab, exc)
                return jsonify({
                    "ok": False,
                    "tab": tab,
                    "generated_at": generated_at,
                    "data": None,
                    "error": str(exc),
                    "meta": {
                        "cache_ttl_s": cache_ttl_s,
                        "trace_id": trace_id,
                        "version": API_VERSION,
                    }
                }), 500
        
        return wrapper
    return decorator


@backend_ui_wrapper_bp.route("/dashboard", methods=["GET"])
@wrap_response("dashboard", cache_ttl_s=5)
def get_dashboard_wrapped():
    """Dashboard endpoint with standardized response wrapper."""
    from copilot_core.api.v1.backend_ui import get_dashboard
    result = get_dashboard()
    return result.get_json() if hasattr(result, 'get_json') else result


@backend_ui_wrapper_bp.route("/zones", methods=["GET"])
@wrap_response("zones", cache_ttl_s=10)
def get_zones_wrapped():
    """Zones endpoint with standardized response wrapper."""
    from copilot_core.api.v1.backend_ui import get_zones
    result = get_zones()
    return result.get_json() if hasattr(result, 'get_json') else result


@backend_ui_wrapper_bp.route("/modules", methods=["GET"])
@wrap_response("modules", cache_ttl_s=10)
def get_modules_wrapped():
    """Modules endpoint with standardized response wrapper."""
    from copilot_core.api.v1.backend_ui import get_modules
    result = get_modules()
    return result.get_json() if hasattr(result, 'get_json') else result


@backend_ui_wrapper_bp.route("/brain", methods=["GET"])
@wrap_response("brain", cache_ttl_s=5)
def get_brain_wrapped():
    """Brain endpoint with standardized response wrapper."""
    from copilot_core.api.v1.backend_ui import get_brain
    result = get_brain()
    return result.get_json() if hasattr(result, 'get_json') else result


@backend_ui_wrapper_bp.route("/mood", methods=["GET"])
@wrap_response("mood", cache_ttl_s=5)
def get_mood_wrapped():
    """Mood endpoint with standardized response wrapper."""
    from copilot_core.api.v1.backend_ui import get_mood
    result = get_mood()
    return result.get_json() if hasattr(result, 'get_json') else result


@backend_ui_wrapper_bp.route("/automation", methods=["GET"])
@wrap_response("automation", cache_ttl_s=10)
def get_automation_wrapped():
    """Automation endpoint with standardized response wrapper."""
    from copilot_core.api.v1.backend_ui import get_automation
    result = get_automation()
    return result.get_json() if hasattr(result, 'get_json') else result


@backend_ui_wrapper_bp.route("/rag", methods=["GET"])
@wrap_response("rag", cache_ttl_s=30)
def get_rag_wrapped():
    """RAG endpoint with standardized response wrapper."""
    from copilot_core.api.v1.backend_ui import get_rag
    result = get_rag()
    return result.get_json() if hasattr(result, 'get_json') else result


@backend_ui_wrapper_bp.route("/media", methods=["GET"])
@wrap_response("media", cache_ttl_s=10)
def get_media_wrapped():
    """Media endpoint with standardized response wrapper."""
    from copilot_core.api.v1.backend_ui import get_media
    result = get_media()
    return result.get_json() if hasattr(result, 'get_json') else result


@backend_ui_wrapper_bp.route("/hardware", methods=["GET"])
@wrap_response("hardware", cache_ttl_s=30)
def get_hardware_wrapped():
    """Hardware endpoint with standardized response wrapper."""
    from copilot_core.api.v1.backend_ui import get_hardware
    result = get_hardware()
    return result.get_json() if hasattr(result, 'get_json') else result


@backend_ui_wrapper_bp.route("/system", methods=["GET"])
@wrap_response("system", cache_ttl_s=60)
def get_system_wrapped():
    """System endpoint with standardized response wrapper."""
    from copilot_core.api.v1.backend_ui import get_system
    result = get_system()
    return result.get_json() if hasattr(result, 'get_json') else result
