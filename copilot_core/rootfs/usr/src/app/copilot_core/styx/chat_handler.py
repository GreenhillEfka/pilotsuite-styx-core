"""
ChatHandler fuer PilotSuite-Styx mit direkter RAG-Integration.

Verarbeitet Chat-Queries mit kontextuellem Wissen aus:
- Lokalen Datenquellen (HA-States, Dokumente, History)
- Optional: Web-Suche via SearXNG
- Direkte interne RAG-Pipeline (BM25 + Semantic + RRF)
- Live Home-Context (Stimmung, Praesenz, Energie, Brain-Aktivitaet)

LLM-Fallback-Kette:
  1. Ollama (lokal, offline, privacy-first)
  2. Cloud API (OpenAI-kompatibel, konfigurierbar)
  → Gesteuert ueber LLMProvider mit Runtime-Routing
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
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

        # 4. Build prompt with RAG context + memory + home context
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
        home_context_used = "Aktueller Haus-Status:" in prompt
        logger.info(
            "Chat complete in %.0fms (sources=%d, type=%s, memory=%s, home_ctx=%s)",
            elapsed_ms, len(rag_results.get("sources", [])), query_type,
            bool(memory_context), home_context_used,
        )

        return {
            "response": response,
            "sources": rag_results.get("sources", []),
            "query_type": query_type,
            "context_used": rag_results.get("results", []),
            "elapsed_ms": round(elapsed_ms, 1),
            "memory_used": bool(memory_context),
            "home_context_used": home_context_used,
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

        # Reciprocal Rank Fusion (RRF) for hybrid search results
        results = self._rrf_merge(results)
        sources = sources[:10]

        return {
            "results": results,
            "sources": sources,
            "query_type": query_type,
        }

    @staticmethod
    def _rrf_merge(results: List[Dict[str, Any]], k: int = 60, top_n: int = 10) -> List[Dict[str, Any]]:
        """Reciprocal Rank Fusion: merge BM25 + Semantic results by rank.

        RRF score = sum(1 / (k + rank_i)) across each search type's ranked list.
        This avoids score normalization issues between different search backends.
        """
        # Group results by search type
        by_type: Dict[str, List[Dict[str, Any]]] = {}
        for r in results:
            st = r.get("search_type", "unknown")
            by_type.setdefault(st, []).append(r)

        # Sort each type's list by score descending
        for st in by_type:
            by_type[st].sort(key=lambda x: x.get("score", 0), reverse=True)

        # Compute RRF scores keyed by doc_id
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, Dict[str, Any]] = {}
        for st, docs in by_type.items():
            for rank, doc in enumerate(docs, start=1):
                doc_id = doc.get("doc_id", f"unknown_{rank}")
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank)
                if doc_id not in doc_map:
                    doc_map[doc_id] = doc

        # Sort by RRF score descending
        ranked = sorted(rrf_scores.items(), key=lambda x: -x[1])
        merged = []
        for doc_id, rrf_score in ranked[:top_n]:
            doc = doc_map[doc_id].copy()
            doc["rrf_score"] = round(rrf_score, 6)
            merged.append(doc)

        return merged

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

    # ── Home Context Builder ─────────────────────────────────────────

    @staticmethod
    def _get_services() -> Dict[str, Any]:
        """Get COPILOT_SERVICES from Flask app context (best effort)."""
        try:
            from flask import current_app
            return current_app.config.get("COPILOT_SERVICES", {}) or {}
        except Exception:
            return {}

    def _build_home_context(self, zone_name: str | None = None) -> str:
        """Build concise home context summary from live service data.

        Gathers data from available services:
        - Mood state + confidence per zone
        - Zone occupancy / presence
        - Recent significant events
        - Time of day / weekday context
        - Energy status
        - Active automations count
        - Brain graph activity summary

        Each source is individually wrapped in try/except so a single
        failure never blocks the other context sources.

        Returns:
            Compact German-language context string (target: <500 tokens).
        """
        services = self._get_services()
        parts: List[str] = []

        # ── 1. Time context ──────────────────────────────────────────
        try:
            now = datetime.now(timezone.utc)
            # Try to get local time via Europe/Berlin (add-on default)
            try:
                import zoneinfo
                local_tz = zoneinfo.ZoneInfo("Europe/Berlin")
                local_now = now.astimezone(local_tz)
            except Exception:
                local_now = now

            hour = local_now.hour
            if 5 <= hour < 10:
                tageszeit = "Morgen"
            elif 10 <= hour < 12:
                tageszeit = "Vormittag"
            elif 12 <= hour < 14:
                tageszeit = "Mittag"
            elif 14 <= hour < 18:
                tageszeit = "Nachmittag"
            elif 18 <= hour < 22:
                tageszeit = "Abend"
            else:
                tageszeit = "Nacht"

            wochentag = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
                         "Freitag", "Samstag", "Sonntag"][local_now.weekday()]
            ist_wochenende = local_now.weekday() >= 5
            we_label = "Wochenende" if ist_wochenende else "Werktag"
            parts.append(
                f"Zeitkontext: {wochentag}, {tageszeit} ({local_now.strftime('%H:%M')} Uhr), {we_label}"
            )
        except Exception as exc:
            logger.debug("Home context: time failed: %s", exc)

        # ── 2. Mood state ────────────────────────────────────────────
        try:
            mood_service = services.get("mood_service")
            if mood_service:
                summary = mood_service.get_summary()
                if summary and summary.get("zones", 0) > 0:
                    comfort = summary.get("average_comfort", 0.5)
                    joy = summary.get("average_joy", 0.5)
                    frugality = summary.get("average_frugality", 0.5)
                    media_zones = summary.get("zones_with_media", 0)
                    zone_count = summary.get("zones", 0)

                    # Determine dominant mood description
                    if comfort >= 0.7 and joy >= 0.6:
                        stimmung = "behaglich und freudig"
                    elif comfort >= 0.6:
                        stimmung = "komfortabel"
                    elif joy >= 0.6:
                        stimmung = "lebhaft"
                    elif frugality >= 0.7:
                        stimmung = "sparsam/energiebewusst"
                    elif comfort < 0.4:
                        stimmung = "unbehaglich"
                    else:
                        stimmung = "neutral"

                    mood_line = (
                        f"Hausstimmung: {stimmung} "
                        f"(Komfort {comfort:.0%}, Freude {joy:.0%}, "
                        f"Sparsamkeit {frugality:.0%})"
                    )
                    if media_zones > 0:
                        mood_line += f", Medien aktiv in {media_zones}/{zone_count} Zonen"
                    parts.append(mood_line)
        except Exception as exc:
            logger.debug("Home context: mood failed: %s", exc)

        # ── 3. Zone occupancy / presence ─────────────────────────────
        try:
            hub_presence = services.get("hub_presence")
            if hub_presence:
                household = hub_presence.get_household_status()
                status = household.get("status", "unknown")
                home_names = household.get("home_names", [])
                away_names = household.get("away_names", [])

                if status == "home":
                    pres_line = f"Praesenz: Alle zuhause ({', '.join(home_names[:5])})"
                elif status == "away":
                    pres_line = "Praesenz: Niemand zuhause"
                elif status == "partial":
                    pres_line = (
                        f"Praesenz: {', '.join(home_names[:5])} zuhause"
                    )
                    if away_names:
                        pres_line += f"; abwesend: {', '.join(away_names[:5])}"
                else:
                    pres_line = "Praesenz: unbekannt"

                # Add occupied rooms if available
                try:
                    rooms = hub_presence.get_rooms()
                    occupied = [
                        r.get("room_name") or r.get("room_id", "?")
                        for r in rooms
                        if r.get("persons_present")
                    ]
                    if occupied:
                        pres_line += f" | Belegte Raeume: {', '.join(occupied[:6])}"
                except Exception:
                    pass

                parts.append(pres_line)
        except Exception as exc:
            logger.debug("Home context: presence failed: %s", exc)

        # ── 4. Recent events summary ─────────────────────────────────
        try:
            # Try the event store via events API singleton
            from copilot_core.api.v1.events_ingest import get_store as _get_event_store
            store = _get_event_store()
            recent = store.list(limit=5)
            if recent:
                event_lines = []
                for evt in recent[-5:]:
                    evt_type = evt.get("type", "?")
                    entity = evt.get("entity_id", "")
                    text = evt.get("text", "")
                    ts = evt.get("ts", "")
                    label = entity or text or evt_type
                    if len(label) > 60:
                        label = label[:57] + "..."
                    event_lines.append(f"  - {evt_type}: {label}")
                if event_lines:
                    parts.append(
                        "Letzte Ereignisse:\n" + "\n".join(event_lines)
                    )
        except Exception as exc:
            logger.debug("Home context: events failed: %s", exc)

        # ── 5. Energy status ─────────────────────────────────────────
        try:
            hub_energy = services.get("hub_energy")
            if hub_energy:
                energy_summary = hub_energy.get_summary()
                if energy_summary:
                    price = energy_summary.get("energy_price_per_kwh", 0)
                    has_pv = energy_summary.get("has_pv_profile", False)
                    targets = energy_summary.get("optimization_targets", 0)
                    energy_line = f"Energie: {price:.2f} EUR/kWh" if price else "Energie: Preis nicht konfiguriert"
                    if has_pv:
                        energy_line += ", PV-Anlage vorhanden"
                    if targets:
                        energy_line += f", {targets} Optimierungsziele"
                    parts.append(energy_line)
        except Exception as exc:
            logger.debug("Home context: energy failed: %s", exc)

        # ── 6. Active automations count ──────────────────────────────
        try:
            zone_automation = services.get("zone_automation")
            if zone_automation and hasattr(zone_automation, "get_zones"):
                zones = zone_automation.get_zones()
                if zones:
                    active_zones = sum(
                        1 for z in zones
                        if isinstance(z, dict) and z.get("light_enabled")
                    )
                    parts.append(
                        f"Zonen-Automationen: {active_zones}/{len(zones)} aktiv"
                    )
        except Exception as exc:
            logger.debug("Home context: automations failed: %s", exc)

        # ── 7. Brain graph activity summary ──────────────────────────
        try:
            hub_brain = services.get("hub_brain_activity")
            if hub_brain:
                status = hub_brain.get_status()
                state = status.state if hasattr(status, "state") else str(status)
                total_pulses = getattr(status, "total_pulses", 0)
                uptime_h = getattr(status, "uptime_seconds", 0) / 3600

                state_labels = {
                    "active": "aktiv",
                    "idle": "bereit",
                    "sleeping": "schlafend",
                }
                state_de = state_labels.get(state, state)
                parts.append(
                    f"Gehirn: {state_de}, {total_pulses} Impulse, "
                    f"Laufzeit {uptime_h:.1f}h"
                )
        except Exception as exc:
            logger.debug("Home context: brain activity failed: %s", exc)

        try:
            brain_graph = services.get("brain_graph_service")
            if brain_graph:
                stats = brain_graph.get_stats()
                nodes = stats.get("node_count", stats.get("nodes", 0))
                edges = stats.get("edge_count", stats.get("edges", 0))
                if nodes or edges:
                    parts.append(
                        f"Wissensgraph: {nodes} Knoten, {edges} Kanten"
                    )
        except Exception as exc:
            logger.debug("Home context: brain graph stats failed: %s", exc)

        # ── 8. Action closure / outcome summary ─────────────────────
        try:
            from copilot_core.action_closure import get_action_closure_store
            from copilot_core.core.action_closure_read_model import build_action_closure_context_block
            from copilot_core.core.proposal_lifecycle_read_model import (
                build_proposal_lifecycle_status_summary,
                describe_proposal_lifecycle_summary,
            )
            from copilot_core.api.v1.notifications import (
                _build_action_closure_follow_up_receipt_summary,
                _describe_action_closure_follow_up_receipt_summary,
            )

            closure_context = build_action_closure_context_block(
                get_action_closure_store(),
                recent_limit=2,
                zone_name=zone_name,
            )
            context_lines = closure_context.to_dict().get("context_lines", [])
            if context_lines:
                parts.append(" | ".join(context_lines))

            receipt_summary = _build_action_closure_follow_up_receipt_summary(recent_limit=2)
            receipt_line = _describe_action_closure_follow_up_receipt_summary(receipt_summary)
            if receipt_line:
                parts.append(receipt_line)

            proposal_summary = build_proposal_lifecycle_status_summary(
                get_action_closure_store(),
                proposal_provider=services.get("suggestion_engine"),
                recent_limit=2,
            ).to_dict()
            proposal_line = describe_proposal_lifecycle_summary(proposal_summary)
            if proposal_line:
                parts.append(proposal_line)
        except Exception as exc:
            logger.debug("Home context: action closure summary failed: %s", exc)

        if not parts:
            return ""

        return "Aktueller Haus-Status:\n" + "\n".join(parts)

    # ── Prompt building ───────────────────────────────────────────────

    def _build_prompt(self, query: str, rag_results: Dict[str, Any],
                      memory_context: str = "") -> str:
        """Build LLM prompt with home context, RAG context, and conversation memory.

        Returns a tuple-style string with system+context sections for the
        single-prompt path (direct Ollama /api/generate).  The structured
        message path (_call_llm with LLMProvider) splits this into proper
        system/user messages.
        """
        results = rag_results.get("results", [])

        prompt_parts = []

        # System instruction
        prompt_parts.append(
            "Du bist PilotSuite Styx, ein intelligenter Smart-Home-Assistent.\n"
            "Beantworte Fragen praezise und hilfreich auf Deutsch.\n"
            "Nutze den aktuellen Haus-Status, um kontextbezogen zu antworten.\n"
            "Wenn du unsicher bist, sage es offen."
        )

        # Live home context (mood, presence, energy, brain, etc.)
        home_context = self._build_home_context()
        if home_context:
            prompt_parts.append(home_context)

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

    @staticmethod
    def _split_system_user(prompt: str) -> tuple:
        """Split a combined prompt into system message and user message.

        The prompt layout from _build_prompt is:
          system instruction\\n\\nhome context\\n\\nmemory\\n\\nRAG\\n\\nFrage: <query>

        We split at the last "Frage: " marker so everything before becomes
        the system message and the question becomes the user message.
        """
        marker = "\n\nFrage: "
        idx = prompt.rfind(marker)
        if idx > 0:
            system_part = prompt[:idx].strip()
            user_part = prompt[idx + len(marker):].strip()
            return system_part, user_part
        # Fallback: everything as user message
        return "", prompt

    def _call_llm(self, prompt: str, model: str) -> str:
        """Call LLM using LLMProvider (Ollama → Cloud fallback).

        Uses proper system/user message separation for better LLM behavior.
        If LLMProvider is unavailable, falls back to direct Ollama /api/generate.
        """
        self._ensure_initialized()

        # Primary path: use LLMProvider with full fallback chain
        if self._llm_provider is not None:
            try:
                system_msg, user_msg = self._split_system_user(prompt)
                messages = []
                if system_msg:
                    messages.append({"role": "system", "content": system_msg})
                messages.append({"role": "user", "content": user_msg or prompt})
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
