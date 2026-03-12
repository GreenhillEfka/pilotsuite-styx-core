"""
ChatHandler fuer PilotSuite-Styx mit direkter RAG-Integration.

Verarbeitet Chat-Queries mit kontextuellem Wissen aus:
- Lokalen Datenquellen (HA-States, Dokumente, History)
- Optional: Web-Suche via SearXNG
- Direkte interne RAG-Pipeline (BM25 + Semantic + RRF)

LLM-Fallback-Kette:
  1. Ollama (lokal, offline, privacy-first)
  2. Cloud API (OpenAI-kompatibel, konfigurierbar)
  → Gesteuert ueber LLMProvider mit Runtime-Routing
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests
from requests import RequestException

logger = logging.getLogger(__name__)

# Default URLs from environment or fallback
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("STYX_LLM_MODEL", "qwen3:0.6b")


class ChatHandler:
    """
    Handler fuer Chat-Queries mit direkter RAG-Pipeline-Integration.

    Uses the internal BM25 + Semantic hybrid search directly instead
    of making HTTP calls to a separate RAG service.

    LLM inference uses LLMProvider for Ollama+Cloud fallback chain.
    Falls back to direct Ollama /api/generate if LLMProvider unavailable.

    ConversationMemory integration:
    - Stores each user query and assistant response
    - Injects relevant conversation history + user preferences into prompts
    - Enables lifelong learning across chat sessions
    """

    def __init__(
        self,
        rag_api_url: Optional[str] = None,
        ollama_url: Optional[str] = None,
        conversation_memory=None,
    ):
        self.ollama_url = (ollama_url or OLLAMA_URL).rstrip("/")
        self._bm25_index = None
        self._searxng_client = None
        self._llm_provider = None
        self._conversation_memory = conversation_memory
        self._initialized = False
        logger.info(
            "ChatHandler initialized (ollama_url=%s, internal_rag=True, memory=%s)",
            self.ollama_url,
            conversation_memory is not None,
        )

    def _ensure_initialized(self) -> None:
        """Lazy-init RAG components and LLM provider on first use."""
        if self._initialized:
            return
        try:
            from copilot_core.rag.bm25 import BM25SqliteIndex
            self._bm25_index = BM25SqliteIndex()
            logger.info("BM25 index loaded (%d docs)", self._bm25_index.doc_count)
        except Exception as exc:
            logger.warning("BM25 index not available: %s", exc)
            self._bm25_index = None

        try:
            from copilot_core.rag.searxng_client import get_searxng_client
            self._searxng_client = get_searxng_client()
        except Exception as exc:
            logger.warning("SearXNG client not available: %s", exc)
            self._searxng_client = None

        # Initialize LLM provider with Ollama+Cloud fallback
        try:
            from copilot_core.llm_provider import LLMProvider
            self._llm_provider = LLMProvider()
            logger.info(
                "LLMProvider loaded (primary=%s, model=%s, cloud=%s)",
                self._llm_provider.primary_provider,
                self._llm_provider.active_model,
                self._llm_provider.has_cloud_fallback,
            )
        except Exception as exc:
            logger.warning("LLMProvider not available, using direct Ollama: %s", exc)
            self._llm_provider = None

        self._initialized = True

    # ── Public API ────────────────────────────────────────────────────

    def set_conversation_memory(self, memory) -> None:
        """Set ConversationMemory instance (for late wiring)."""
        self._conversation_memory = memory
        logger.info("ConversationMemory wired into ChatHandler")

    def handle_query(
        self,
        query: str,
        user_id: str,
        use_web: bool = False,
        model: str = "",
        conversation_id: str = "",
    ) -> Dict[str, Any]:
        """
        Process a chat query with RAG context and conversation memory.

        Args:
            query: User question
            user_id: User identifier for history
            use_web: Enable web search via SearXNG
            model: Ollama model for inference
            conversation_id: Optional conversation thread ID for history

        Returns:
            Dict with response, sources, query_type, context_used
        """
        model = model or DEFAULT_MODEL
        start = time.perf_counter()

        logger.info(
            "Chat query (user=%s, web=%s, model=%s): %s",
            user_id, use_web, model, query[:120],
        )

        # 0. Store user message in ConversationMemory
        if self._conversation_memory:
            try:
                self._conversation_memory.store_message(
                    role="user", content=query,
                    conversation_id=conversation_id or None,
                )
            except Exception as exc:
                logger.warning("Failed to store user message in memory: %s", exc)

        # 1. Classify query
        query_type = self._classify_query(query, use_web)

        # 2. RAG search (internal)
        rag_results = self._search_internal(query, use_web, query_type)

        # 3. Get conversation memory context
        memory_context = self._get_memory_context(query, conversation_id)

        # 4. Build prompt with RAG context + memory
        prompt = self._build_prompt(query, rag_results, memory_context)

        # 5. LLM inference (Ollama → Cloud fallback)
        response = self._call_llm(prompt, model)

        # 6. Store assistant response in ConversationMemory
        if self._conversation_memory:
            try:
                self._conversation_memory.store_message(
                    role="assistant", content=response,
                    conversation_id=conversation_id or None,
                )
            except Exception as exc:
                logger.warning("Failed to store assistant response in memory: %s", exc)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Chat complete in %.0fms (sources=%d, type=%s, memory=%s)",
            elapsed_ms, len(rag_results.get("sources", [])), query_type,
            bool(memory_context),
        )

        return {
            "response": response,
            "sources": rag_results.get("sources", []),
            "query_type": query_type,
            "context_used": rag_results.get("results", []),
            "elapsed_ms": round(elapsed_ms, 1),
            "memory_used": bool(memory_context),
        }

    # ── Internal RAG search ───────────────────────────────────────────

    def _classify_query(self, query: str, use_web: bool) -> str:
        """Classify query type using the internal query router."""
        try:
            from copilot_core.rag.query_router import classify_query
            classification = classify_query(query)
            if use_web or classification.use_web_search:
                return classification.query_type.value
            return "local"
        except Exception:
            return "web" if use_web else "local"

    def _search_internal(
        self, query: str, use_web: bool, query_type: str
    ) -> Dict[str, Any]:
        """Search using the internal RAG pipeline directly."""
        self._ensure_initialized()

        results: List[Dict[str, Any]] = []
        sources: List[Dict[str, Any]] = []

        # BM25 lexical search
        if self._bm25_index is not None:
            try:
                bm25_hits = self._bm25_index.search(query, top_k=10)
                for hit in bm25_hits:
                    results.append({
                        "content": hit.text,
                        "score": hit.score,
                        "source": hit.namespace,
                        "doc_id": hit.doc_id,
                        "search_type": "bm25",
                    })
                    sources.append({
                        "id": hit.doc_id,
                        "score": hit.score,
                        "source": hit.namespace,
                    })
            except Exception as exc:
                logger.warning("BM25 search failed: %s", exc)

        # Semantic search via VectorStore
        try:
            from copilot_core.vector_store import get_vector_store, get_embedding_engine
            vs = get_vector_store()
            ee = get_embedding_engine()
            if vs and ee:
                embedding = ee.embed(query)
                if embedding is not None:
                    sem_hits = vs.search(embedding, top_k=10)
                    for sh in sem_hits:
                        results.append({
                            "content": sh.get("text", ""),
                            "score": sh.get("score", 0.0),
                            "source": sh.get("namespace", "vector"),
                            "doc_id": sh.get("id", ""),
                            "search_type": "semantic",
                        })
                        sources.append({
                            "id": sh.get("id", ""),
                            "score": sh.get("score", 0.0),
                            "source": "semantic",
                        })
        except Exception as exc:
            logger.debug("Semantic search not available: %s", exc)

        # Web search via SearXNG (optional)
        if use_web and self._searxng_client:
            try:
                web_results = self._searxng_client.search(query, max_results=5)
                for wr in web_results:
                    results.append({
                        "content": wr.snippet,
                        "score": wr.score,
                        "source": wr.url,
                        "doc_id": wr.url,
                        "search_type": "web",
                    })
                    sources.append({
                        "id": wr.url,
                        "score": wr.score,
                        "source": "web",
                    })
            except Exception as exc:
                logger.warning("Web search failed: %s", exc)

        # Sort by score descending, take top 10
        results.sort(key=lambda r: r.get("score", 0), reverse=True)
        results = results[:10]
        sources = sources[:10]

        return {
            "results": results,
            "sources": sources,
            "query_type": query_type,
        }

    # ── Conversation Memory ──────────────────────────────────────────

    def _get_memory_context(self, query: str, conversation_id: str = "") -> str:
        """Get relevant context from ConversationMemory.

        Combines:
        - Relevant past conversations (topic-matched)
        - User preferences (learned over time)
        - Recent conversation history (if conversation_id given)
        """
        if not self._conversation_memory:
            return ""

        parts = []
        try:
            # Get relevant past conversations + preferences
            relevant = self._conversation_memory.get_relevant_context(query, limit=3)
            if relevant:
                parts.append(relevant)

            # Get user preferences for prompt injection
            prefs = self._conversation_memory.get_preferences_for_prompt()
            if prefs:
                parts.append(prefs)

            # Get recent conversation history for this thread
            if conversation_id:
                history = self._conversation_memory.get_conversation_history(
                    conversation_id, limit=6
                )
                if history:
                    hist_lines = []
                    for msg in history[-6:]:
                        role_label = "Nutzer" if msg["role"] == "user" else "Assistent"
                        hist_lines.append(f"  {role_label}: {msg['content'][:150]}")
                    parts.append("\nGespraechsverlauf:\n" + "\n".join(hist_lines))

        except Exception as exc:
            logger.warning("Failed to get memory context: %s", exc)

        return "\n".join(parts)

    # ── Prompt building ───────────────────────────────────────────────

    def _build_prompt(self, query: str, rag_results: Dict[str, Any],
                      memory_context: str = "") -> str:
        """Build LLM prompt with RAG context and conversation memory."""
        results = rag_results.get("results", [])

        prompt_parts = []

        # System instruction
        prompt_parts.append(
            "Du bist PilotSuite Styx, ein intelligenter Smart-Home-Assistent.\n"
            "Beantworte Fragen praezise und hilfreich auf Deutsch.\n"
            "Wenn du unsicher bist, sage es offen."
        )

        # Memory context (preferences + history)
        if memory_context:
            prompt_parts.append(memory_context)

        # RAG context
        if results:
            context_parts = []
            for i, result in enumerate(results[:8], start=1):
                content = result.get("content", "")
                source = result.get("source", "unknown")
                score = result.get("score", 0)
                if content:
                    context_parts.append(
                        f"[Quelle {i}] (Score: {score:.3f}, Quelle: {source})\n{content}"
                    )
            if context_parts:
                prompt_parts.append(
                    "Relevanter Kontext:\n\n" + "\n\n".join(context_parts)
                )

        # User question
        prompt_parts.append(f"Frage: {query}")

        return "\n\n".join(prompt_parts)

    # ── LLM inference with fallback ─────────────────────────────────

    def _call_llm(self, prompt: str, model: str) -> str:
        """Call LLM using LLMProvider (Ollama → Cloud fallback).

        If LLMProvider is unavailable, falls back to direct Ollama /api/generate.
        """
        self._ensure_initialized()

        # Primary path: use LLMProvider with full fallback chain
        if self._llm_provider is not None:
            try:
                messages = [{"role": "user", "content": prompt}]
                result = self._llm_provider.chat(
                    messages=messages,
                    model=model or None,
                    temperature=0.7,
                )
                content = result.get("content", "")
                provider = result.get("provider", "unknown")
                if content and provider != "none":
                    logger.info("LLM response via %s (model=%s)", provider, model)
                    return content
                # Provider returned empty or "none" — fall through to direct call
                logger.warning("LLMProvider returned empty (provider=%s), trying direct Ollama", provider)
            except Exception as exc:
                logger.warning("LLMProvider failed: %s, trying direct Ollama", exc)

        # Fallback: direct Ollama /api/generate
        return self._call_ollama_direct(prompt, model)

    def _call_ollama_direct(self, prompt: str, model: str) -> str:
        """Direct Ollama /api/generate call (fallback when LLMProvider unavailable)."""
        generate_url = f"{self.ollama_url}/api/generate"

        payload = {
            "model": model or DEFAULT_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
            },
        }

        try:
            resp = requests.post(generate_url, json=payload, timeout=120)
            if resp.status_code != 200:
                logger.error("Ollama failed (status=%s, model=%s)", resp.status_code, model)
                return f"Entschuldigung, LLM nicht verfuegbar (Status: {resp.status_code})."

            return resp.json().get("response", "")

        except RequestException as exc:
            logger.exception("Ollama request failed: %s", exc)
            return f"Entschuldigung, LLM-Verbindung fehlgeschlagen: {exc}"
