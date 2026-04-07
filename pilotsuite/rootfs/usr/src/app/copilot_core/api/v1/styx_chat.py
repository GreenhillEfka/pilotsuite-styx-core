"""
PilotSuite-Styx Chat API Endpoint.

Bietet REST-Endpoint für Chat-Queries mit RAG-API Integration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token
from copilot_core.api.validation import validate_json
from copilot_core.api.v1.schemas import ChatRequestSchema
from copilot_core.styx.chat_handler import ChatHandler

logger = logging.getLogger(__name__)

bp = Blueprint("styx_chat", __name__, url_prefix="/api/styx")


def _now_iso() -> str:
    """Get current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


# ── Auth guard ──────────────────────────────────────────────────────────

@bp.before_request
def _require_auth() -> Optional[Any]:
    if not validate_token(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401


# ── Request/Response Schemas ────────────────────────────────────────────

@dataclass
class ChatRequest:
    """Request-Schema für Chat-Endpoint."""
    query: str
    user_id: str
    use_web: bool = False
    model: str = "qwen3:0.6b"

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "ChatRequest":
        return cls(
            query=str(data.get("query", "")).strip(),
            user_id=str(data.get("user_id", "anonymous")),
            use_web=bool(data.get("use_web", False)),
            model=str(data.get("model", "qwen3:0.6b")),
        )


# ── Configuration ───────────────────────────────────────────────────────

# Singleton ChatHandler fallback (uses internal RAG pipeline directly)
_chat_handler: Optional[ChatHandler] = None


def _get_chat_handler() -> ChatHandler:
    """Liefert singleton ChatHandler mit ConversationMemory-Integration."""
    global _chat_handler
    
    # Try to get from Flask app config first (initialized in core_setup.py)
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        if services and services.get("chat_handler"):
            return services["chat_handler"]
    except Exception:
        pass
    
    # Fallback: create singleton
    if _chat_handler is None:
        # Try to get ConversationMemory from services
        conversation_memory = None
        try:
            from flask import current_app
            services = current_app.config.get("COPILOT_SERVICES", {})
            conversation_memory = services.get("conversation_memory")
        except RuntimeError:
            pass  # Outside app context
        _chat_handler = ChatHandler(conversation_memory=conversation_memory)
    return _chat_handler


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /api/styx/chat
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/chat", methods=["POST"])
@validate_json(ChatRequestSchema)
def styx_chat(body: ChatRequestSchema) -> Any:
    """PilotSuite-Styx Chat-Endpoint with Pydantic validation.

    Validates: query (1–10000 chars), user_id (required), model, use_web.
    """
    try:
        logger.info(
            "Styx chat request (user_id=%s, query=%s, use_web=%s, model=%s)",
            body.user_id,
            body.query[:100],
            body.use_web,
            body.model,
        )

        handler = _get_chat_handler()
        result = handler.handle_query(
            query=body.query,
            user_id=body.user_id,
            use_web=body.use_web,
            model=body.model,
            conversation_id=getattr(body, "conversation_id", ""),
        )

        logger.info(
            "Styx chat response (query_type=%s, sources_count=%s, response_length=%s)",
            result.get("query_type", "local"),
            len(result.get("sources", [])),
            len(result.get("response", "")),
        )

        return jsonify({
            "ok": True,
            "response": result.get("response", ""),
            "sources": result.get("sources", []),
            "query_type": result.get("query_type", "local"),
            "context_used": result.get("context_used", []),
            "home_context_used": result.get("home_context_used", False),
        })

    except Exception as exc:
        logger.exception("Styx chat endpoint failed: %s", exc)
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT: GET /api/styx/health
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/health", methods=["GET"])
def styx_health() -> Any:
    """
    Health-Check für Styx Chat-Service.
    
    Returns:
        Status von RAG-API und Ollama
    """
    import requests as _requests
    import os

    ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

    rag_status = "unknown"
    ollama_status = "unknown"

    # RAG internal check (BM25 index)
    try:
        from copilot_core.rag.bm25 import BM25SqliteIndex
        idx = BM25SqliteIndex()
        rag_status = "ok" if idx.doc_count >= 0 else "empty"
    except Exception:
        rag_status = "not_initialized"

    # Ollama check
    try:
        resp = _requests.get(f"{ollama_url}/api/tags", timeout=5)
        ollama_status = "ok" if resp.status_code == 200 else "error"
    except Exception:
        ollama_status = "unreachable"

    status = {
        "rag_pipeline": rag_status,
        "ollama": ollama_status,
        "ollama_url": ollama_url,
        "rag_type": "internal",
    }

    all_ok = rag_status in ("ok", "empty") and ollama_status == "ok"

    return jsonify({
        "ok": all_ok,
        "services": status,
    }), 200 if all_ok else 503


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT: GET /api/styx/health/backend
# ══════════════════════════════════════════════════════════════════════════

def _check_backend_service(service_name: str, service_obj) -> Dict[str, Any]:
    """
    Check a single backend service health.
    
    Args:
        service_name: Name of the service
        service_obj: Service instance or None
        
    Returns:
        Dict with health status
    """
    import json as _json
    
    if service_obj is None:
        return {
            "service": service_name,
            "status": "missing",
            "healthy": False,
            "message": "Service not initialized",
        }
    
    # Check if service has health check method
    if hasattr(service_obj, "health_check") or hasattr(service_obj, "get_status"):
        try:
            if hasattr(service_obj, "health_check"):
                health = service_obj.health_check()
            else:
                health = service_obj.get_status()
            
            # Ensure health is JSON serializable
            if not isinstance(health, dict):
                health = {"status": str(health)}
            
            # Remove non-serializable objects
            def _sanitize(obj):
                if isinstance(obj, dict):
                    return {k: _sanitize(v) for k, v in obj.items() if not _is_callable_or_unserializable(v)}
                elif isinstance(obj, (list, tuple)):
                    return [_sanitize(v) for v in obj if not _is_callable_or_unserializable(v)]
                elif isinstance(obj, (str, int, float, bool)) or obj is None:
                    return obj
                else:
                    return str(obj)
            
            def _is_callable_or_unserializable(obj):
                return callable(obj) or isinstance(obj, (type, Exception))
            
            health = _sanitize(health)
            
            return {
                "service": service_name,
                "status": "ok",
                "healthy": True,
                "data": health,
            }
        except Exception as e:
            return {
                "service": service_name,
                "status": "error",
                "healthy": False,
                "message": str(e),
            }
    
    # Fallback: service exists but no health method
    return {
        "service": service_name,
        "status": "ok",
        "healthy": True,
        "message": "Service running (no health check method)",
    }


@bp.route("/health/backend", methods=["GET"])
def styx_health_backend() -> Any:
    """
    Backend Services Health Check Endpoint.
    
    Monitors all services registered in COPILOT_SERVICES:
    - Core services (brain_graph, conversation_memory, etc.)
    - Module services (habitus, mood, energy, etc.)
    - Hub services (hub_dashboard, hub_zones, etc.)
    
    Returns:
        Full health status of all backend services
    """
    from flask import current_app
    
    # Get all backend services
    services = current_app.config.get("COPILOT_SERVICES", {})
    
    # Check each service
    service_health = {}
    unhealthy_services = []
    
    for service_name, service_obj in services.items():
        health = _check_backend_service(service_name, service_obj)
        service_health[service_name] = health
        
        if not health.get("healthy", False):
            unhealthy_services.append(service_name)
    
    # Determine overall status
    overall_ok = len(unhealthy_services) == 0
    
    # Build response
    response = {
        "ok": overall_ok,
        "timestamp": _now_iso(),
        "total_services": len(service_health),
        "unhealthy_services": unhealthy_services,
        "services": service_health,
    }
    
    return jsonify(response), 200 if overall_ok else 503


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT: GET /api/styx/memory
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/memory", methods=["GET"])
def styx_memory_stats() -> Any:
    """Get ConversationMemory statistics and learned preferences.

    Returns memory store stats (total messages, preferences, span)
    and the current set of learned user preferences.
    """
    from flask import current_app

    services = current_app.config.get("COPILOT_SERVICES", {})
    conv_memory = services.get("conversation_memory")

    if not conv_memory:
        return jsonify({"ok": False, "error": "ConversationMemory not initialized"}), 503

    try:
        stats = conv_memory.get_stats()
        prefs = conv_memory.get_user_preferences()
        pref_list = [
            {"key": p.key, "value": p.value, "confidence": p.confidence,
             "source": p.source, "mention_count": p.mention_count}
            for p in prefs
        ]

        return jsonify({
            "ok": True,
            "stats": stats,
            "preferences": pref_list,
            "preference_count": len(pref_list),
        })
    except Exception as exc:
        logger.exception("Memory stats failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT: GET /api/styx/memory/history
# ══════════════════════════════════════════════════════════════════════════

@bp.route("/memory/history", methods=["GET"])
def styx_memory_history() -> Any:
    """Get conversation history for a specific conversation thread.

    Query params:
        conversation_id: Thread ID
        limit: Max messages (default 20)
    """
    from flask import current_app

    services = current_app.config.get("COPILOT_SERVICES", {})
    conv_memory = services.get("conversation_memory")

    if not conv_memory:
        return jsonify({"ok": False, "error": "ConversationMemory not initialized"}), 503

    conversation_id = request.args.get("conversation_id", "")
    limit = min(100, max(1, int(request.args.get("limit", 20))))

    try:
        history = conv_memory.get_conversation_history(conversation_id, limit=limit)
        return jsonify({
            "ok": True,
            "conversation_id": conversation_id,
            "messages": history,
            "count": len(history),
        })
    except Exception as exc:
        logger.exception("Memory history failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500
