"""Conversation API — chat endpoint + OpenAI-compatible /v1/chat/completions."""

import logging
import time

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

conversation_bp = Blueprint("conversation", __name__, url_prefix="/api/v1/conversation")
openai_compat_bp = Blueprint("openai_compat", __name__, url_prefix="/v1")


def _get_llm() -> object | None:
    return current_app.config.get("COPILOT_LLM")


def _get_memory():
    return current_app.config.get("COPILOT_MEMORY")


def _store_exchange(messages: list, response_content: str) -> None:
    """Best-effort store of conversation exchange in memory."""
    memory = _get_memory()
    if memory is None:
        return
    try:
        for msg in messages:
            if msg.get("role") == "user":
                memory.store_message(role="user", content=msg.get("content", ""))
        if response_content:
            memory.store_message(role="assistant", content=response_content)
    except Exception:
        _LOGGER.debug("Failed to store conversation in memory", exc_info=True)


# ------------------------------------------------------------------
# Native conversation API
# ------------------------------------------------------------------

@conversation_bp.route("", methods=["GET"])
@require_token
def conversation_status():
    """Return conversation/LLM status."""
    llm = _get_llm()
    if llm is None:
        return jsonify({"ok": False, "error": "LLM provider not initialized"}), 503
    return jsonify({"ok": True, "status": llm.status()})


@conversation_bp.route("/chat", methods=["POST"])
@require_token
def conversation_chat():
    """Native chat endpoint — simpler than OpenAI compat."""
    llm = _get_llm()
    if llm is None:
        return jsonify({"ok": False, "error": "LLM provider not initialized"}), 503

    data = request.get_json(silent=True) or {}
    messages = data.get("messages")
    if not messages or not isinstance(messages, list):
        return jsonify({"ok": False, "error": "messages[] required"}), 400

    model = data.get("model")
    temperature = data.get("temperature")
    max_tokens = data.get("max_tokens")

    result = llm.chat(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    _store_exchange(messages, result.get("content", ""))
    return jsonify({"ok": True, **result})


# ------------------------------------------------------------------
# OpenAI-compatible API (/v1/chat/completions, /v1/models)
# ------------------------------------------------------------------

@openai_compat_bp.route("/chat/completions", methods=["POST"])
@require_token
def chat_completions():
    """OpenAI-compatible chat completions endpoint."""
    llm = _get_llm()
    if llm is None:
        return jsonify({"error": {"message": "LLM provider not initialized", "type": "server_error"}}), 503

    data = request.get_json(silent=True) or {}
    messages = data.get("messages")
    if not messages or not isinstance(messages, list):
        return jsonify({"error": {"message": "messages[] required", "type": "invalid_request_error"}}), 400

    model = data.get("model", "")
    temperature = data.get("temperature")
    max_tokens = data.get("max_tokens")
    tools = data.get("tools")

    result = llm.chat(
        messages=messages,
        tools=tools,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    content = result.get("content", "")
    tool_calls = result.get("tool_calls")
    provider = result.get("provider", "unknown")
    used_model = model or getattr(llm, "active_model", "pilotsuite")

    response = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": used_model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "x_pilotsuite_provider": provider,
    }

    if tool_calls:
        response["choices"][0]["message"]["tool_calls"] = tool_calls
        response["choices"][0]["finish_reason"] = "tool_calls"

    _store_exchange(messages, content)
    return jsonify(response)


@openai_compat_bp.route("/models", methods=["GET"])
@require_token
def list_models():
    """OpenAI-compatible models listing."""
    llm = _get_llm()
    if llm is None:
        return jsonify({"data": [], "object": "list"})

    catalog = llm.model_catalog()
    models = []
    seen = set()

    for section in ("offline", "cloud"):
        for model_id in catalog.get(section, {}).get("models", []):
            if model_id not in seen:
                seen.add(model_id)
                models.append({
                    "id": model_id,
                    "object": "model",
                    "created": 0,
                    "owned_by": f"pilotsuite-{section}",
                })

    return jsonify({"data": models, "object": "list"})
