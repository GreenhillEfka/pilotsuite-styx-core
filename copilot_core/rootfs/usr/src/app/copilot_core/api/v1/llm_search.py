"""LLM Search API — Direct Web Search via SearXNG.

Provides endpoints for direct web search integration with LLM context injection.
"""

from flask import Blueprint, jsonify, request
from copilot_core.llm_provider import LLMProvider
from copilot_core.api.security import validate_token as _validate_token

bp = Blueprint("llm_search", __name__, url_prefix="/api/v1/llm")

_llm_provider = None


def init_llm_search(llm_provider: LLMProvider):
    """Initialize LLM search endpoint with provider instance."""
    global _llm_provider
    _llm_provider = llm_provider


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


@bp.route("/search", methods=["POST"])
def search():
    """Execute web search via SearXNG (if enabled).

    Request body:
    {
        "query": "search term",
        "direct": true  // if true, return search result as-is
    }

    Response:
    {
        "ok": true,
        "query": "search term",
        "result": "Search result string"
    }
    """
    if not _llm_provider:
        return jsonify({"ok": False, "error": "LLM provider not initialized"}), 503

    data = request.get_json(force=True, silent=True) or {}
    query = str(data.get("query", "")).strip()

    if not query:
        return jsonify({"ok": False, "error": "Missing query parameter"}), 400

    if not _llm_provider.searxng_enabled:
        return jsonify({
            "ok": False,
            "error": "SearXNG web search disabled",
            "searxng_enabled": False,
            "searxng_base_url": _llm_provider.searxng_base_url,
        }), 400

    try:
        result = _llm_provider.search_web(query)
        return jsonify({
            "ok": True,
            "query": query,
            "result": result,
        })
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.exception("LLM search failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/status", methods=["GET"])
def search_status():
    """Return SearXNG web search configuration status."""
    if not _llm_provider:
        return jsonify({"ok": False, "error": "LLM provider not initialized"}), 503

    return jsonify({
        "ok": True,
        "searxng_enabled": _llm_provider.searxng_enabled,
        "searxng_base_url": _llm_provider.searxng_base_url,
        "searxng_timeout": _llm_provider.searxng_timeout,
    })
