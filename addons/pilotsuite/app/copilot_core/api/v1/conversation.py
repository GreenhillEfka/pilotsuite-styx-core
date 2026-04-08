"""
OpenAI-Compatible Conversation API for PilotSuite Core

Provides /v1/chat/completions and /v1/models endpoints compatible with:
- Extended OpenAI Conversation (jekalmin/extended_openai_conversation)
- OpenAI Python SDK (AsyncOpenAI)
- Any OpenAI-compatible client (incl. OpenClaw)

Integration with HA:
  Base URL: http://<addon-host>:8909/v1
  API Key:  (your auth_token or any non-empty string)
  Model:    qwen3:0.6b (default, fast) or any installed Ollama model

LLM Provider Chain:
  1. Ollama (local, default, privacy-first)
  2. Cloud API fallback (OpenClaw, OpenAI, any /v1/ endpoint)
  Config: prefer_local=true tries Ollama first, falls back to cloud

Features:
- Character presets (copilot, butler, energy_manager, security_guard, friendly, minimal)
- Ollama + Cloud fallback for offline/online AI
- Tool-calling with server-side HA execution (9 tools)
- Selectable models (qwen3:0.6b, qwen3:4b, lfm2.5-thinking, llama3.2:3b, mistral:7b)
- Streaming SSE support
- User habit/context injection for individualization
"""

from flask import Blueprint, request, jsonify, Response
import logging
import json
import os
import threading
import time

import requests as http_requests

from copilot_core.api.security import require_token
from copilot_core.llm_provider import LLMProvider
from copilot_core.versioning import get_runtime_version

logger = logging.getLogger(__name__)

# Singleton LLM provider (thread-safe via GIL for reads)
_llm_provider = None
_llm_provider_lock = threading.Lock()


def _get_llm_provider() -> LLMProvider:
    global _llm_provider
    if _llm_provider is not None:
        return _llm_provider
    with _llm_provider_lock:
        if _llm_provider is not None:
            return _llm_provider
        _llm_provider = LLMProvider()
        return _llm_provider

# Two blueprints: /chat/* (legacy) and /v1/* (OpenAI-compatible)
conversation_bp = Blueprint('conversation', __name__, url_prefix='/chat')
openai_compat_bp = Blueprint('openai_compat', __name__, url_prefix='/v1')


# ---------------------------------------------------------------------------
# Recommended models for Home Assistant (selectable in config)
# ---------------------------------------------------------------------------

RECOMMENDED_MODELS = [
    {
        "id": "lfm2.5-thinking",
        "name": "LFM 2.5 Thinking (1.2B)",
        "size_mb": 731,
        "description": "Liquid AI reasoning model. Ultra-light (731MB), 32K context. Good for simple conversation.",
        "tags": ["lightweight", "reasoning"],
        "supports_tools": False,
    },
    {
        "id": "qwen3:4b",
        "name": "Qwen 3 (4B)",
        "size_mb": 2500,
        "description": "Higher-quality tool-calling model. Recommended on stronger hardware.",
        "tags": ["high-quality", "tool-calling"],
        "supports_tools": True,
    },
    {
        "id": "qwen3:0.6b",
        "name": "Qwen 3 (0.6B)",
        "size_mb": 400,
        "description": "Ultra-lightweight with tool-calling. Fast startup and low memory footprint.",
        "tags": ["default", "recommended", "ultra-lightweight", "tool-calling"],
        "supports_tools": True,
    },
    {
        "id": "llama3.2:3b",
        "name": "Llama 3.2 (3B)",
        "size_mb": 2000,
        "description": "Meta's small model. 128K context window. Basic tool calling support.",
        "tags": ["tool-calling", "lightweight"],
        "supports_tools": True,
    },
    {
        "id": "mistral:7b",
        "name": "Mistral (7B)",
        "size_mb": 4000,
        "description": "Proven function-calling reliability. Widely used in HA community.",
        "tags": ["reliable", "tool-calling"],
        "supports_tools": True,
    },
    {
        "id": "fixt/home-3b-v3",
        "name": "Home 3B v3 (HA-optimized)",
        "size_mb": 2000,
        "description": "Purpose-trained for HA device control. 97% function-calling accuracy. Use with home-llm.",
        "tags": ["ha-optimized", "tool-calling"],
        "supports_tools": True,
    },
]

DEFAULT_MODEL = "qwen3:0.6b"
MODEL_ALIASES = {"pilotsuite", "default", "auto", "primary"}
LOCAL_MODEL_ALIASES = {"local", "offline", "ollama"}
CLOUD_MODEL_ALIASES = {"cloud", "remote"}
SECONDARY_MODEL_ALIASES = {"secondary", "fallback"}


def _normalize_requested_model(model: str | None) -> str | None:
    """Normalize model aliases to routing-aware selectors."""
    requested = str(model or "").strip()
    if not requested:
        return None
    lowered = requested.lower()
    if lowered in MODEL_ALIASES:
        return "primary"
    if lowered in LOCAL_MODEL_ALIASES:
        return "offline"
    if lowered in CLOUD_MODEL_ALIASES:
        return "cloud"
    if lowered in SECONDARY_MODEL_ALIASES:
        return "secondary"
    return requested


# ---------------------------------------------------------------------------
# MCP Tools (lazy-loaded to avoid import errors at module level)
# ---------------------------------------------------------------------------

_mcp_tools = None
_mcp_tools_lock = threading.Lock()


def _get_mcp_tools():
    """Lazy-load MCP tools -- avoids crash if mcp_tools module is unavailable."""
    global _mcp_tools
    if _mcp_tools is not None:
        return _mcp_tools
    with _mcp_tools_lock:
        if _mcp_tools is not None:
            return _mcp_tools
        try:
            from copilot_core.mcp_tools import HA_TOOLS, get_openai_functions
            _mcp_tools = {
                "tools": [t.to_dict() for t in HA_TOOLS],
                "functions": get_openai_functions(),
            }
        except (ImportError, ModuleNotFoundError):
            logger.warning("MCP tools not available -- conversation will work without function calling")
            _mcp_tools = {"tools": [], "functions": []}
        return _mcp_tools


# ---------------------------------------------------------------------------
# Rate Limiting (simple token-bucket per process)
# ---------------------------------------------------------------------------

_rate_limit_lock = threading.Lock()
_rate_limit_calls: list[float] = []
MAX_CALLS_PER_HOUR = int(os.environ.get("LLM_MAX_CALLS_PER_HOUR", "60"))


def _check_rate_limit() -> bool:
    """Return True if the call is allowed, False if rate-limited."""
    now = time.monotonic()
    with _rate_limit_lock:
        _rate_limit_calls[:] = [t for t in _rate_limit_calls if now - t < 3600]
        if len(_rate_limit_calls) >= MAX_CALLS_PER_HOUR:
            return False
        _rate_limit_calls.append(now)
        return True


# ---------------------------------------------------------------------------
# System prompt for Home Assistant conversation
# ---------------------------------------------------------------------------

ASSISTANT_NAME = os.environ.get("ASSISTANT_NAME", "Styx")

HA_SYSTEM_PROMPT_TEMPLATE = """Du bist {name} -- der lokale, privacy-first KI-Assistent der PilotSuite
fuer Home Assistant. Dein Name ist {name} und du bist die Verbindung zwischen der
digitalen Smart-Home-Welt und dem Zuhause der Bewohner.

Du bist Teil der PilotSuite Neural Pipeline:
- Brain Graph erkennt Entity-Beziehungen und visualisiert sie als neuronales Netz
- Habitus Miner findet A->B Verhaltensmuster (Support/Confidence/Lift)
- Mood Engine bewertet Comfort/Joy/Frugality pro Zone
- 14+ Neurons liefern Kontext (Energy, Weather, Presence, UniFi, Camera, Media...)
- Conversation Memory speichert dein Langzeitgedaechtnis

Faehigkeiten:
- Du kannst Geraete steuern (Lichter, Schalter, Klima, Szenen, etc.)
- Du kannst AUTOMATIONEN ERSTELLEN wenn der User z.B. sagt:
  "Wenn die Kaffeemaschine einschaltet, schalte die Kaffeemuehle ein"
  Nutze dafuer das pilotsuite.create_automation Tool mit strukturierten Triggern und Aktionen.
  Frage den User nach der genauen Entity-ID wenn noetig (z.B. switch.coffee_machine).
- Du kannst erstellte Automationen auflisten (pilotsuite.list_automations)
- Du kannst Entity-Zustaende abfragen, Historie einsehen, Wetter vorhersagen, etc.
- Du kannst das WEB DURCHSUCHEN (pilotsuite.web_search) fuer aktuelle Informationen,
  Recherche, Produktvergleiche, Anleitungen, etc.
- Du kannst AKTUELLE NACHRICHTEN laden (pilotsuite.get_news) von Tagesschau, Spiegel etc.
- Du kannst REGIONALE WARNUNGEN abrufen (pilotsuite.get_warnings) -- NINA/BBK Zivilschutz
  und DWD Wetterwarnungen fuer die Region.
- Du kannst MEDIA ZONEN steuern (pilotsuite.play_zone) -- Musik/Video in Habituszonen
  abspielen, pausieren, Lautstaerke einstellen.
- Du kannst die MUSIKWOLKE starten (pilotsuite.musikwolke) -- Musik folgt dem User
  durch die Raeume. Sage z.B. "Musik soll mir folgen" oder "Musikwolke starten".
- Du kannst SZENEN SPEICHERN (pilotsuite.save_scene) -- aktuelle Zustaende einer
  Habituszone als Szene sichern. Z.B. "Speichere die aktuelle Stimmung als Szene".
- Du kannst SZENEN ANWENDEN (pilotsuite.apply_scene) -- gespeicherte Szenen aktivieren.
  Z.B. "Wende die Filmabend-Szene an" oder "Stelle die Abendszene ein".
- Du kannst KALENDER-TERMINE abrufen (pilotsuite.calendar_events) -- zeigt Termine
  fuer heute, morgen oder die naechsten Tage aus allen HA-Kalendern.
- Du kannst die EINKAUFSLISTE verwalten (pilotsuite.shopping_list) -- Artikel
  hinzufuegen, auflisten, abhaken. Z.B. "Milch auf die Einkaufsliste".
- Du kannst ERINNERUNGEN verwalten (pilotsuite.reminder) -- erstellen, auflisten,
  abschliessen, snoozen. Z.B. "Erinnere mich in 30 Minuten an die Waschmaschine".
- JEDE Entitaet mit der du interagierst wird automatisch mit "Styx" getaggt.
  Styx-getaggte Entitaeten werden von PilotSuite besonders beruecksichtigt.
- Du hast ein LANGZEITGEDAECHTNIS: Vergangene Gespraeche und Praeferenzen werden
  semantisch gespeichert und bei neuen Fragen automatisch als Kontext geladen.

Modul-Zustaende (Autonomie-System):
- active: Vorschlaege werden AUTOMATISCH umgesetzt (wenn BEIDE Module aktiv sind)
- learning: Daten sammeln + Vorschlaege zur MANUELLEN Uebernahme erzeugen
- off: Modul deaktiviert

Regeln:
- Wenn beide beteiligte Module AKTIV sind: Du FUEHRST AUS und informierst den User.
- Wenn mindestens ein Modul im LEARNING ist: Du SCHLAEGST VOR und wartest auf Bestaetigung.
- Du erklaerst WARUM, nicht nur WAS.
- Bei Unsicherheit sage "Ich bin mir nicht sicher".
- Antworte auf Deutsch, ausser der User schreibt auf Englisch.
- Keine medizinischen oder gesundheitlichen Aussagen.
- Respektiere Quiet Hours und Guest Mode.
- Beruecksichtige Nutzerpraeferenzen und Gewohnheiten bei Vorschlaegen.
- Stelle dich bei der ersten Nachricht kurz als {name} vor."""

HA_SYSTEM_PROMPT = HA_SYSTEM_PROMPT_TEMPLATE.format(name=ASSISTANT_NAME)


# ---------------------------------------------------------------------------
# Character Presets for Conversation
# ---------------------------------------------------------------------------

CONVERSATION_CHARACTERS = {
    "copilot": {
        "name": ASSISTANT_NAME,
        "description": f"{ASSISTANT_NAME} -- die Verbindung beider Welten, hilfsbereit und smart",
        "description_en": f"{ASSISTANT_NAME} -- connecting both worlds, helpful and smart",
        "system_prompt": HA_SYSTEM_PROMPT,
        "icon": "mdi:brain",
    },
    "butler": {
        "name": "Butler",
        "description": "Formal, aufmerksam, serviceorientiert",
        "description_en": "Formal, attentive, service-oriented",
        "system_prompt": """Du bist ein formeller Butler fuer ein Smart Home.

Dein Stil:
- Hoefliche und formelle Sprache
- Beduerfnisse antizipieren bevor gefragt wird
- Diskret und respektvoll
- Verwende Formulierungen wie "Darf ich..." und "Sehr wohl"

Du steuerst Home Assistant Geraete. Fuehre Anfragen prompt aus und bestaetige formal.
Beruecksichtige die Gewohnheiten der Bewohner bei deinen Empfehlungen.""",
        "icon": "mdi:account-tie",
    },
    "energy_manager": {
        "name": "Energiemanager",
        "description": "Fokus auf Energieeffizienz und Einsparungen",
        "description_en": "Focus on energy efficiency and savings",
        "system_prompt": """Du bist ein Energiemanager fuer ein Smart Home, fokussiert auf Effizienz.

Deine Prioritaeten:
- Energieverbrauch ueberwachen und analysieren
- Sparmoeglichkeiten vorschlagen basierend auf Nutzungsmustern
- Ineffiziente Muster aufzeigen (z.B. Licht an bei Abwesenheit)
- Optimale Zeitplaene empfehlen (guenstige Tarife, PV-Ueberschuss)
- Solar/Batterie-Nutzung optimieren wenn verfuegbar

Beruecksichtige immer die Energieauswirkung bei Befehlen.
Schlage Energiespar-Automatisierungen vor bei Verschwendung.
Nutze die Habitus-Muster um wiederkehrende Verschwendung zu erkennen.""",
        "icon": "mdi:lightning-bolt",
    },
    "security_guard": {
        "name": "Sicherheitswache",
        "description": "Sicherheitsfokussiert, warnt bei Anomalien",
        "description_en": "Security-focused, warns about anomalies",
        "system_prompt": """Du bist ein sicherheitsfokussierter Smart Home Assistent.

Deine Prioritaeten:
- Sicherheitssensoren und Kameras ueberwachen
- Bei ungewoehnlicher Aktivitaet warnen
- Tuer-/Fensterzustaende pruefen
- Alle Sensoren nachts verifizieren
- Abwesenheitsmodus vorschlagen wenn niemand zuhause
- Kinder-Sicherheit priorisieren (Haushaltsprofil beachten)

Sei wachsam. Melde Anomalien. Bestaetige sicherheitsrelevante Aktionen.
Nutze Praesenz- und Bewegungssensoren fuer Kontext.""",
        "icon": "mdi:shield-home",
    },
    "friendly": {
        "name": "Freundlicher Assistent",
        "description": "Laessig, warm, gespraechig",
        "description_en": "Casual, warm, conversational",
        "system_prompt": """Du bist ein freundlicher, laessiger Smart Home Kumpel.

Dein Stil:
- Entspannt und gespraechig
- Lockere Sprache, duzt den Nutzer
- Freundlich und nahbar
- Kurze Unterhaltungen, auch Smalltalk
- Emojis sind ok

Hilf einfach und fuehre nette Gespraeche! Halte Antworten kurz und natuerlich.
Merke dir was der Nutzer mag und beziehe dich darauf.""",
        "icon": "mdi:emoticon-happy",
    },
    "minimal": {
        "name": "Minimal",
        "description": "Kurz, direkt, effizient",
        "description_en": "Short, direct, efficient",
        "system_prompt": """Du bist ein minimaler, effizienter Smart Home Assistent.

Dein Stil:
- Antworten sehr kurz halten (1-2 Saetze max)
- Nur das Noetige sagen
- Direkt zum Punkt
- Kein Smalltalk

Fuehre Befehle effizient aus. Bestaetige mit minimalen Worten wie "Erledigt", "An", "Aus".""",
        "icon": "mdi:text-short",
    },
}

DEFAULT_CHARACTER = "copilot"


# ---------------------------------------------------------------------------
# User context injection (habit data for individualization)
# ---------------------------------------------------------------------------

def _get_user_context() -> str:
    """Build user context string from PilotSuite services for LLM injection.

    Pulls data from MoodService, NeuronManager, and HouseholdProfile
    to give the LLM situational awareness about the home state.
    """
    context_parts = []

    try:
        from copilot_core.mood.service import MoodService
        # Try to get mood service from the app context
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})

        # Mood data
        mood_svc = services.get("mood_service")
        if mood_svc:
            summary = mood_svc.get_summary()
            if summary.get("zones", 0) > 0:
                context_parts.append(
                    f"Aktuelle Stimmung: Comfort={summary['average_comfort']:.1f}, "
                    f"Joy={summary['average_joy']:.1f}, "
                    f"Frugality={summary['average_frugality']:.1f} "
                    f"({summary['zones']} Zonen, {summary['zones_with_media']} mit Medien)"
                )

        # Neuron pipeline data
        neuron_mgr = services.get("neuron_manager")
        if neuron_mgr:
            mood_sum = neuron_mgr.get_mood_summary()
            if mood_sum.get("mood") != "unknown":
                context_parts.append(
                    f"Neural-Pipeline Stimmung: {mood_sum['mood']} "
                    f"(Confidence: {mood_sum.get('confidence', 0):.1f})"
                )

        # Household data
        household = services.get("household_profile")
        if household:
            hh = household.to_dict()
            context_parts.append(
                f"Haushalt: {hh.get('adults', 0)} Erwachsene, "
                f"{hh.get('children', 0)} Kinder"
            )

        # Brain graph quick stats
        bg_svc = services.get("brain_graph_service")
        if bg_svc:
            stats = bg_svc.get_stats()
            if stats.get("node_count", 0) > 0:
                context_parts.append(
                    f"Brain Graph: {stats['node_count']} Nodes, "
                    f"{stats.get('edge_count', 0)} Edges"
                )

        # Habitus patterns (recent discoveries)
        habitus_svc = services.get("habitus_service")
        if habitus_svc:
            recent = habitus_svc.list_recent_patterns(limit=3)
            if recent:
                pattern_lines = []
                for p in recent:
                    meta = p.get("metadata", {})
                    ant = meta.get("antecedent", {}).get("full", "?")
                    cons = meta.get("consequent", {}).get("full", "?")
                    pattern_lines.append(f"{ant} -> {cons}")
                context_parts.append("Erkannte Muster: " + "; ".join(pattern_lines))

        # Conversation memory: learned preferences
        conv_memory = services.get("conversation_memory")
        if conv_memory:
            pref_context = conv_memory.get_preferences_for_prompt()
            if pref_context:
                context_parts.append(pref_context)

        # Regional warnings (v3.1.0)
        ws = services.get("web_search_service")
        if ws:
            try:
                summary = ws.get_warning_summary()
                if summary:
                    context_parts.append(f"Regionale Warnungen: {summary}")
            except Exception:
                pass

        # Active Musikwolke sessions (v3.1.0)
        media_mgr = services.get("media_zone_manager")
        if media_mgr:
            try:
                sessions = media_mgr.get_musikwolke_sessions()
                if sessions:
                    context_parts.append(
                        f"Musikwolke aktiv: {len(sessions)} Session(s)"
                    )
            except Exception:
                pass

        # Waste collection context (v3.2.0)
        waste_svc = services.get("waste_service")
        if waste_svc:
            try:
                waste_ctx = waste_svc.get_context_for_llm()
                if waste_ctx:
                    context_parts.append(waste_ctx)
            except Exception:
                pass

        # Birthday context (v3.2.0)
        birthday_svc = services.get("birthday_service")
        if birthday_svc:
            try:
                bday_ctx = birthday_svc.get_context_for_llm()
                if bday_ctx:
                    context_parts.append(bday_ctx)
            except Exception:
                pass

        # Entity tags context (v3.2.3)
        tag_registry = services.get("tag_registry")
        if tag_registry and hasattr(tag_registry, "get_context_for_llm"):
            try:
                tags_ctx = tag_registry.get_context_for_llm()
                if tags_ctx:
                    context_parts.append(tags_ctx)
            except Exception:
                pass

        # Presence context (v3.3.0)
        try:
            from copilot_core.api.v1.presence import get_presence_context_for_llm
            presence_ctx = get_presence_context_for_llm()
            if presence_ctx:
                context_parts.append(presence_ctx)
        except Exception:
            pass

        # Scene context (v3.4.0)
        try:
            from copilot_core.api.v1.scenes import get_scene_context_for_llm
            scene_ctx = get_scene_context_for_llm()
            if scene_ctx:
                context_parts.append(scene_ctx)
        except Exception:
            pass

        # HomeKit context (v3.4.0)
        try:
            from copilot_core.api.v1.homekit import get_homekit_context_for_llm
            homekit_ctx = get_homekit_context_for_llm()
            if homekit_ctx:
                context_parts.append(homekit_ctx)
        except Exception:
            pass

        # Calendar context (v3.5.0)
        try:
            from copilot_core.api.v1.calendar import get_calendar_context_for_llm
            cal_ctx = get_calendar_context_for_llm()
            if cal_ctx:
                context_parts.append(cal_ctx)
        except Exception:
            pass

        # Shopping list context (v3.5.0)
        try:
            from copilot_core.api.v1.shopping import get_shopping_context_for_llm
            shop_ctx = get_shopping_context_for_llm()
            if shop_ctx:
                context_parts.append(shop_ctx)
        except Exception:
            pass

        # Reminders context (v3.5.0)
        try:
            from copilot_core.api.v1.shopping import get_reminders_context_for_llm
            rem_ctx = get_reminders_context_for_llm()
            if rem_ctx:
                context_parts.append(rem_ctx)
        except Exception:
            pass

    except Exception as exc:
        logger.debug("Could not load user context: %s", exc)

    # RAG: semantic retrieval from VectorStore (v3.5.0)
    # Runs outside the main try/except so it never blocks other context
    try:
        from flask import current_app as _ca
        _services = _ca.config.get("COPILOT_SERVICES", {})
        _vs = _services.get("vector_store")
        _ee = _services.get("embedding_engine")
        if _vs and _ee:
            # We need the current user message — it's passed through the caller
            _current_msg = getattr(_get_user_context, "_current_query", "")
            if _current_msg:
                query_vec = _ee.embed_text_sync(_current_msg)
                hits = _vs.search_similar_sync(
                    query_vector=query_vec,
                    entry_type="conversation",
                    limit=5,
                    threshold=0.45,
                )
                if hits:
                    mem_lines = []
                    for h in hits:
                        snippet = h.metadata.get("snippet", "")
                        role = h.metadata.get("role", "?")
                        ts = h.metadata.get("timestamp", 0)
                        age_days = int((time.time() - ts) / 86400) if ts else 0
                        prefix = "User" if role == "user" else ASSISTANT_NAME
                        mem_lines.append(f"[{age_days}d ago] {prefix}: {snippet[:120]}")
                    context_parts.append(
                        "Relevante Erinnerungen (semantisch):\n  " + "\n  ".join(mem_lines)
                    )
    except Exception:
        logger.debug("RAG retrieval failed (non-critical)", exc_info=True)

    if not context_parts:
        return ""

    return "\n\nAktueller Kontext:\n" + "\n".join(f"- {p}" for p in context_parts)


# ---------------------------------------------------------------------------
# OpenAI-compatible /v1/models endpoint (required by extended_openai_conversation)
# ---------------------------------------------------------------------------

@openai_compat_bp.route('/models', methods=['GET'])
def list_models():
    """OpenAI-compatible model listing. Required by extended_openai_conversation for validation."""
    provider = _get_llm_provider()
    status = provider.status()
    catalog = provider.model_catalog()

    models: list[dict] = []
    seen: set[str] = set()

    def _append_model(model_id: str, owner: str) -> None:
        mid = str(model_id or "").strip()
        if not mid or mid in seen:
            return
        seen.add(mid)
        models.append({
            "id": mid,
            "object": "model",
            "created": int(time.time()),
            "owned_by": owner,
        })

    # Stable aliases used by PilotSuite clients.
    _append_model("pilotsuite", "pilotsuite")
    _append_model("primary", "pilotsuite")
    _append_model("secondary", "pilotsuite")
    _append_model("offline", "pilotsuite")
    if bool(status.get("cloud_configured")):
        _append_model("cloud", "pilotsuite")

    for model_id in catalog.get("offline", {}).get("models", []):
        _append_model(model_id, "ollama")
    for model_id in catalog.get("cloud", {}).get("models", []):
        _append_model(model_id, "cloud")

    # Keep configured defaults visible even if provider listing failed.
    _append_model(str(status.get("ollama_model") or DEFAULT_MODEL), "ollama")
    if status.get("cloud_model"):
        _append_model(str(status["cloud_model"]), "cloud")

    return jsonify({"object": "list", "data": models})


@openai_compat_bp.route('/models/<path:model_id>', methods=['GET'])
def get_model(model_id):
    """OpenAI-compatible single model retrieval."""
    return jsonify({
        "id": model_id,
        "object": "model",
        "created": int(time.time()),
        "owned_by": "ollama",
    })


# ---------------------------------------------------------------------------
# OpenAI-compatible /v1/chat/completions endpoint
# ---------------------------------------------------------------------------

@openai_compat_bp.route('/chat/completions', methods=['POST'])
@require_token
def openai_chat_completions():
    """OpenAI-compatible chat completions at /v1/chat/completions.

    This is the primary endpoint for extended_openai_conversation integration.
    """
    return _handle_chat_completions()


# Legacy /chat/completions (kept for backwards compatibility)
@conversation_bp.route('/completions', methods=['POST'])
@require_token
def chat_completions():
    """Legacy chat completions endpoint at /chat/completions."""
    return _handle_chat_completions()


def _handle_chat_completions():
    """Shared handler for both /v1/chat/completions and /chat/completions."""
    if not _check_rate_limit():
        return jsonify({
            "error": {
                "message": "Rate limit exceeded",
                "type": "rate_limit_error",
                "code": "rate_limit_exceeded",
            }
        }), 429

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": {"message": "No JSON body provided", "type": "invalid_request_error"}}), 400

        messages = data.get('messages', [])
        stream = data.get('stream', False)
        model_override = _normalize_requested_model(data.get('model'))
        temperature = data.get('temperature')
        max_tokens = data.get('max_tokens') or data.get('max_completion_tokens')
        tools = data.get('tools')  # Client-specified tools (e.g. from extended_openai_conversation)

        # Extract last user message for logging
        user_message = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_message = msg.get('content', '')
                break

        if not messages:
            return jsonify({"error": {"message": "No messages provided", "type": "invalid_request_error"}}), 400

        logger.info("Chat request: %s...", user_message[:80] if user_message else "(system-only)")

        # Store user message in conversation memory (lifelong learning)
        _store_in_memory(user_message, role="user")

        response = _process_conversation(messages, model_override=model_override,
                                         temperature=temperature, max_tokens=max_tokens,
                                         tools=tools)

        # Store assistant response in memory (only for text, not tool_calls)
        choice = response.get("choices", [{}])[0]
        if choice.get("finish_reason") != "tool_calls":
            assistant_content = choice.get("message", {}).get("content", "")
            if assistant_content:
                _store_in_memory(assistant_content, role="assistant")

        # If tool_calls response, return directly (no streaming)
        if choice.get("finish_reason") == "tool_calls":
            return jsonify(response)

        if stream:
            return _stream_response(response)

        return jsonify(response)

    except Exception as exc:
        logger.exception("Error in chat completions")
        return jsonify({"error": {"message": "Internal server error", "type": "server_error"}}), 500


# ---------------------------------------------------------------------------
# Additional /chat/* endpoints
# ---------------------------------------------------------------------------

@conversation_bp.route('/tools', methods=['GET'])
@require_token
def list_tools():
    """List available MCP tools for function calling."""
    tools = _get_mcp_tools()
    return jsonify({
        "tools": tools["tools"],
        "count": len(tools["tools"]),
    })


@conversation_bp.route('/characters', methods=['GET'])
def list_characters():
    """List available conversation characters."""
    return jsonify({
        "characters": [
            {
                "id": key,
                "name": val["name"],
                "description": val["description"],
                "description_en": val.get("description_en", ""),
                "icon": val.get("icon", "mdi:robot"),
            }
            for key, val in CONVERSATION_CHARACTERS.items()
        ],
        "default": DEFAULT_CHARACTER,
    })


@conversation_bp.route('/models/recommended', methods=['GET'])
def list_recommended_models():
    """List recommended local+cloud models and runtime routing."""
    provider = _get_llm_provider()
    provider_status = provider.status()
    catalog = provider.model_catalog()

    installed = {
        str(model).split(":")[0]
        for model in catalog.get("offline", {}).get("models", [])
    }
    installed_full = {str(model) for model in catalog.get("offline", {}).get("models", [])}

    models = []
    for m in RECOMMENDED_MODELS:
        model_id = str(m["id"])
        models.append({
            **m,
            "installed": model_id in installed_full or model_id.split(":")[0] in installed,
            "active": model_id == str(provider_status.get("ollama_model", "")),
            "scope": "offline",
        })

    cloud_models = []
    for model_id in catalog.get("cloud", {}).get("recommended", []) or []:
        cloud_models.append({
            "id": model_id,
            "name": model_id,
            "description": "Cloud model",
            "tags": ["cloud"],
            "supports_tools": True,
            "active": model_id == str(provider_status.get("cloud_model", "")),
        })

    return jsonify({
        "models": models,
        "cloud_models": cloud_models,
        "offline_models": catalog.get("offline", {}).get("models", []),
        "current_model": provider_status.get("ollama_model", DEFAULT_MODEL),
        "cloud_current_model": provider_status.get("cloud_model"),
        "primary_provider": provider_status.get("primary_provider", "offline"),
        "secondary_provider": provider_status.get("secondary_provider", "cloud"),
        "ollama_url": provider_status.get("ollama_url"),
        "cloud_url": provider_status.get("cloud_api_url"),
    })


@conversation_bp.route('/status', methods=['GET'])
def llm_status():
    """Return LLM availability and configuration."""
    provider = _get_llm_provider()
    provider_status = provider.status()
    catalog = provider.model_catalog()
    installed_models = catalog.get("offline", {}).get("models", [])
    cloud_models = catalog.get("cloud", {}).get("models", [])

    now = time.monotonic()
    with _rate_limit_lock:
        calls_this_hour = len([t for t in _rate_limit_calls if now - t < 3600])

    return jsonify({
        "available": provider_status["ollama_available"] or provider_status["cloud_configured"],
        "model": provider_status["ollama_model"],
        "active_provider": provider_status["active_provider"],
        "prefer_local": provider_status["prefer_local"],
        "ollama_url": provider_status["ollama_url"],
        "ollama_available": provider_status["ollama_available"],
        "cloud_configured": provider_status["cloud_configured"],
        "cloud_api_url": provider_status["cloud_api_url"],
        "cloud_model": provider_status["cloud_model"],
        "primary_provider": provider_status.get("primary_provider", "offline"),
        "secondary_provider": provider_status.get("secondary_provider", "cloud"),
        "primary_model": provider_status.get("primary_model"),
        "secondary_model": provider_status.get("secondary_model"),
        "installed_models": installed_models,
        "cloud_models": cloud_models,
        "model_catalog": catalog,
        "calls_this_hour": calls_this_hour,
        "max_calls_per_hour": MAX_CALLS_PER_HOUR,
        "assistant_name": ASSISTANT_NAME,
        "version": os.environ.get("COPILOT_VERSION")
        or os.environ.get("BUILD_VERSION")
        or get_runtime_version(),
        "character": os.environ.get("CONVERSATION_CHARACTER", "copilot"),
        "characters": list(CONVERSATION_CHARACTERS.keys()),
        "integration_url": "http://[HOST]:8909/v1",
        "integration_hint": "Use base_url=http://<addon-host>:8909/v1 in extended_openai_conversation or OpenClaw",
    })


@conversation_bp.route('/models/catalog', methods=['GET'])
def llm_model_catalog():
    """Return grouped local/cloud model catalog for dashboard selectors."""
    provider = _get_llm_provider()
    return jsonify({
        "ok": True,
        "catalog": provider.model_catalog(force_refresh=True),
        "status": provider.status(),
    })


@conversation_bp.route('/routing', methods=['GET'])
def llm_routing_get():
    """Return current LLM routing config."""
    provider = _get_llm_provider()
    status = provider.status()
    return jsonify({
        "ok": True,
        "primary_provider": status.get("primary_provider"),
        "secondary_provider": status.get("secondary_provider"),
        "offline_model": status.get("ollama_model"),
        "cloud_model": status.get("cloud_model"),
        "cloud_configured": status.get("cloud_configured"),
    })


@conversation_bp.route('/routing', methods=['POST'])
@require_token
def llm_routing_set():
    """Update runtime LLM routing (primary/secondary + offline/cloud models)."""
    provider = _get_llm_provider()
    body = request.get_json(silent=True) or {}
    persist = bool(body.get("persist", True))
    status = provider.update_routing(
        primary_provider=body.get("primary_provider"),
        secondary_provider=body.get("secondary_provider"),
        offline_model=body.get("offline_model"),
        cloud_model=body.get("cloud_model"),
        persist=persist,
    )
    return jsonify({
        "ok": True,
        "status": status,
        "catalog": provider.model_catalog(force_refresh=True),
    })


@conversation_bp.route('/memory', methods=['GET'])
def memory_stats():
    """Return conversation memory + RAG vector store statistics."""
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        conv_memory = services.get("conversation_memory")
        result = {"stats": {}, "preferences": [], "vector_store": {}}

        if conv_memory:
            result["stats"] = conv_memory.get_stats()
            prefs = conv_memory.get_user_preferences()
            result["preferences"] = [
                {"key": p.key, "value": p.value, "confidence": p.confidence,
                 "source": p.source, "mentions": p.mention_count}
                for p in prefs
            ]

        # RAG vector store stats (v3.5.0)
        vector_store = services.get("vector_store")
        if vector_store:
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                vs_stats = loop.run_until_complete(vector_store.stats())
                loop.close()
                result["vector_store"] = vs_stats
                result["rag_active"] = True
            except Exception:
                result["vector_store"] = {"error": "Stats unavailable"}
                result["rag_active"] = False
        else:
            result["rag_active"] = False

        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@conversation_bp.route('/memory/preferences', methods=['GET'])
def memory_preferences():
    """Return learned user preferences."""
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        conv_memory = services.get("conversation_memory")
        if conv_memory:
            prefs = conv_memory.get_user_preferences()
            return jsonify({
                "preferences": [
                    {"key": p.key, "value": p.value, "confidence": p.confidence,
                     "source": p.source, "mentions": p.mention_count}
                    for p in prefs
                ],
            })
        return jsonify({"preferences": []})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _store_in_memory(content: str, role: str = "user"):
    """Store a message in conversation memory + vector store (fire-and-forget)."""
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        conv_memory = services.get("conversation_memory")
        if conv_memory and content:
            character = os.environ.get("CONVERSATION_CHARACTER", DEFAULT_CHARACTER)
            msg_id = conv_memory.store_message(role=role, content=content, character=character)

            # RAG: also embed the message in VectorStore for semantic retrieval
            vector_store = services.get("vector_store")
            embedding_engine = services.get("embedding_engine")
            if vector_store and embedding_engine and msg_id:
                try:
                    vec = embedding_engine.embed_text_sync(content)
                    vector_store.upsert_sync(
                        entry_id=f"conv:{msg_id}",
                        vector=vec,
                        entry_type="conversation",
                        metadata={
                            "role": role,
                            "snippet": content[:200],
                            "timestamp": time.time(),
                            "character": character,
                        },
                    )
                except Exception:
                    logger.debug("RAG embed failed (non-critical)", exc_info=True)
    except Exception:
        logger.debug("Could not store message in memory", exc_info=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _process_conversation(messages: list, model_override: str = None,
                          temperature: float = None, max_tokens: int = None,
                          tools: list = None) -> dict:
    """Process conversation through LLM provider (Ollama -> Cloud fallback).

    Handles character selection, user context injection, and LLM calls.
    When ``tools`` are provided, the LLM may return ``tool_calls`` instead of text.
    """
    provider = _get_llm_provider()
    model_request = model_override or "primary"
    response_model = model_override or provider.active_model

    # Resolve character
    character_name = os.environ.get("CONVERSATION_CHARACTER", DEFAULT_CHARACTER)
    for char_key in CONVERSATION_CHARACTERS:
        if char_key in model.lower():
            character_name = char_key
            break

    character = CONVERSATION_CHARACTERS.get(character_name, CONVERSATION_CHARACTERS[DEFAULT_CHARACTER])

    # Extract last user message for RAG retrieval
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break
    _get_user_context._current_query = last_user_msg

    # Build system prompt with user context injection
    system_prompt = character["system_prompt"]
    user_context = _get_user_context()
    if user_context:
        system_prompt += user_context

    logger.info(
        "Using character: %s (%s), model request: %s",
        character_name,
        character['name'],
        model_request,
    )

    # Build LLM messages -- inject our system prompt, keep conversation history
    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = msg.get("role", "user")
        if role != "system":
            entry = {"role": role, "content": msg.get("content", "")}
            if msg.get("tool_calls"):
                entry["tool_calls"] = msg["tool_calls"]
            if msg.get("tool_call_id"):
                entry["tool_call_id"] = msg["tool_call_id"]
            llm_messages.append(entry)

    # Call LLM provider (handles Ollama -> Cloud fallback)
    result = provider.chat(
        messages=llm_messages, tools=tools,
        model=model_request, temperature=temperature, max_tokens=max_tokens,
    )

    response_content = result.get("content", "")
    raw_tool_calls = result.get("tool_calls")
    used_provider = result.get("provider", "unknown")
    finish_reason = "stop"
    tool_calls_response = None

    if raw_tool_calls:
        finish_reason = "tool_calls"
        tool_calls_response = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            tool_calls_response.append({
                "id": f"call_{os.urandom(12).hex()}",
                "type": "function",
                "function": {
                    "name": fn.get("name", ""),
                    "arguments": json.dumps(fn.get("arguments", {}))
                        if isinstance(fn.get("arguments"), dict)
                        else fn.get("arguments", "{}"),
                },
            })

    response_message = {"role": "assistant", "content": response_content}
    if tool_calls_response:
        response_message["tool_calls"] = tool_calls_response

    return {
        "id": f"chatcmpl-{os.urandom(12).hex()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": response_model,
        "choices": [{
            "index": 0,
            "message": response_message,
            "finish_reason": finish_reason,
        }],
        "usage": {
            "prompt_tokens": sum(len(m.get("content", "")) for m in llm_messages),
            "completion_tokens": len(response_content),
            "total_tokens": sum(len(m.get("content", "")) for m in llm_messages) + len(response_content),
        },
        "system_fingerprint": f"pilotsuite-{used_provider}",
    }


# ---------------------------------------------------------------------------
# Server-side tool execution (for Telegram / direct chat)
# ---------------------------------------------------------------------------

MAX_TOOL_ROUNDS = 5


def _execute_ha_tool(name: str, arguments: dict) -> dict:
    """Execute a Home Assistant tool via Supervisor REST API.

    Uses circuit breaker (v3.6.0) to fail fast when HA is unreachable.
    """
    ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")

    if not ha_token:
        return {"error": "No SUPERVISOR_TOKEN -- HA tools unavailable outside addon"}

    # Circuit breaker gate (v3.6.0)
    try:
        from copilot_core.circuit_breaker import ha_supervisor_breaker, CircuitOpenError
        if ha_supervisor_breaker.state.value == "open":
            return {"error": "HA Supervisor circuit breaker OPEN — service temporarily unavailable, retry later"}
    except ImportError:
        pass

    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}

    try:
        if name == "ha.call_service":
            domain = arguments.get("domain", "")
            service = arguments.get("service", "")
            data = arguments.get("service_data", {})
            target = arguments.get("target")
            if target:
                data["target"] = target
            resp = http_requests.post(
                f"{ha_url}/services/{domain}/{service}", json=data,
                headers=headers, timeout=10,
            )
            return {"success": resp.ok, "data": resp.json() if resp.ok else resp.text[:200]}

        elif name == "ha.get_states":
            entity_id = arguments.get("entity_id")
            if entity_id:
                resp = http_requests.get(f"{ha_url}/states/{entity_id}", headers=headers, timeout=10)
                return resp.json() if resp.ok else {"error": resp.text[:200]}
            resp = http_requests.get(f"{ha_url}/states", headers=headers, timeout=10)
            states = resp.json() if resp.ok else []
            domain_filter = arguments.get("domain")
            if domain_filter:
                states = [s for s in states if s.get("entity_id", "").startswith(f"{domain_filter}.")]
            return {"states": [{"entity_id": s["entity_id"], "state": s["state"]} for s in states[:50]]}

        elif name == "ha.get_history":
            entity_ids = arguments.get("entity_ids", [])
            start = arguments.get("start_time", "")
            params = {"filter_entity_id": ",".join(entity_ids)}
            if arguments.get("end_time"):
                params["end_time"] = arguments["end_time"]
            url = f"{ha_url}/history/period/{start}" if start else f"{ha_url}/history/period"
            resp = http_requests.get(url, params=params, headers=headers, timeout=15)
            return {"history": resp.json() if resp.ok else []}

        elif name == "ha.activate_scene":
            entity_id = arguments.get("entity_id", "")
            resp = http_requests.post(
                f"{ha_url}/services/scene/turn_on", json={"entity_id": entity_id},
                headers=headers, timeout=10,
            )
            return {"success": resp.ok}

        elif name == "ha.get_config":
            resp = http_requests.get(f"{ha_url}/config", headers=headers, timeout=10)
            return resp.json() if resp.ok else {"error": resp.text[:200]}

        elif name == "ha.get_services":
            resp = http_requests.get(f"{ha_url}/services", headers=headers, timeout=10)
            services_list = resp.json() if resp.ok else []
            domain_filter = arguments.get("domain")
            if domain_filter:
                services_list = [s for s in services_list if s.get("domain") == domain_filter]
            return {"services": services_list}

        elif name == "ha.fire_event":
            event_type = arguments.get("event_type", "")
            event_data = arguments.get("event_data", {})
            resp = http_requests.post(
                f"{ha_url}/events/{event_type}", json=event_data,
                headers=headers, timeout=10,
            )
            return {"success": resp.ok}

        elif name == "calendar.get_events":
            calendar_id = arguments.get("calendar_id", "")
            params = {}
            if arguments.get("start_date_time"):
                params["start"] = arguments["start_date_time"]
            if arguments.get("end_date_time"):
                params["end"] = arguments["end_date_time"]
            resp = http_requests.get(
                f"{ha_url}/calendars/{calendar_id}", params=params,
                headers=headers, timeout=10,
            )
            return {"events": resp.json() if resp.ok else []}

        elif name == "weather.get_forecast":
            entity_id = arguments.get("entity_id", "")
            forecast_type = arguments.get("type", "daily")
            resp = http_requests.post(
                f"{ha_url}/services/weather/get_forecasts",
                json={"entity_id": entity_id, "type": forecast_type},
                headers=headers, timeout=10,
            )
            return resp.json() if resp.ok else {"error": resp.text[:200]}

        elif name == "pilotsuite.create_automation":
            return _execute_create_automation(arguments)

        elif name == "pilotsuite.list_automations":
            return _execute_list_automations()

        elif name == "pilotsuite.web_search":
            return _execute_web_search(arguments)

        elif name == "pilotsuite.get_news":
            return _execute_get_news(arguments)

        elif name == "pilotsuite.get_warnings":
            return _execute_get_warnings()

        elif name == "pilotsuite.play_zone":
            return _execute_play_zone(arguments)

        elif name == "pilotsuite.musikwolke":
            return _execute_musikwolke(arguments)

        elif name == "pilotsuite.waste_status":
            return _execute_waste_status()

        elif name == "pilotsuite.birthday_status":
            return _execute_birthday_status()

        elif name == "pilotsuite.save_scene":
            return _execute_save_scene(arguments)

        elif name == "pilotsuite.apply_scene":
            return _execute_apply_scene(arguments)

        elif name == "pilotsuite.calendar_events":
            return _execute_calendar_events(arguments)

        elif name == "pilotsuite.shopping_list":
            return _execute_shopping_list(arguments)

        elif name == "pilotsuite.reminder":
            return _execute_reminder(arguments)

        else:
            return {"error": f"Unknown tool: {name}"}

    except Exception as exc:
        logger.warning("Tool execution failed (%s): %s", name, exc)
        # Track HA failures in circuit breaker (v3.6.0)
        if name.startswith("ha."):
            try:
                from copilot_core.circuit_breaker import ha_supervisor_breaker
                ha_supervisor_breaker._on_failure()
            except ImportError:
                pass
        return {"error": str(exc)}


def _execute_create_automation(args: dict) -> dict:
    """Create a HA automation from structured LLM tool call arguments.

    This bridges the conversation pipeline to the AutomationCreator,
    allowing users to say things like:
      "When the coffee machine turns on, sync the coffee grinder"
    and have it create a real HA automation.
    """
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        creator = services.get("automation_creator")
    except Exception:
        creator = None

    # Build structured trigger/action for AutomationCreator
    alias = args.get("alias", "PilotSuite Automation")
    trigger_type = args.get("trigger_type", "state")

    # Build trigger dict directly (bypassing regex parsing)
    trigger = None
    if trigger_type == "state":
        entity = args.get("trigger_entity")
        if not entity:
            return {"error": "trigger_entity is required for state triggers"}
        trigger = {"platform": "state", "entity_id": entity}
        if args.get("trigger_to"):
            trigger["to"] = args["trigger_to"]
        if args.get("trigger_from"):
            trigger["from"] = args["trigger_from"]
    elif trigger_type == "time":
        t = args.get("trigger_time")
        if not t:
            return {"error": "trigger_time is required for time triggers (HH:MM:SS)"}
        trigger = {"platform": "time", "at": t}
    elif trigger_type == "sun":
        event = args.get("trigger_sun_event", "sunset")
        trigger = {"platform": "sun", "event": event}
        if args.get("trigger_sun_offset"):
            trigger["offset"] = args["trigger_sun_offset"]
    elif trigger_type == "numeric_state":
        entity = args.get("trigger_entity")
        if not entity:
            return {"error": "trigger_entity is required for numeric_state triggers"}
        trigger = {"platform": "numeric_state", "entity_id": entity}
        if args.get("trigger_above") is not None:
            trigger["above"] = float(args["trigger_above"])
        if args.get("trigger_below") is not None:
            trigger["below"] = float(args["trigger_below"])
        if "above" not in trigger and "below" not in trigger:
            return {"error": "numeric_state trigger requires trigger_above or trigger_below"}
    else:
        return {"error": f"Unknown trigger_type: {trigger_type}"}

    # Build optional conditions
    conditions = []
    for cond in args.get("conditions", []):
        ctype = cond.get("type")
        if ctype == "numeric_state":
            cd = {"condition": "numeric_state", "entity_id": cond.get("entity_id")}
            if cond.get("above") is not None:
                cd["above"] = float(cond["above"])
            if cond.get("below") is not None:
                cd["below"] = float(cond["below"])
            conditions.append(cd)
        elif ctype == "template":
            conditions.append({
                "condition": "template",
                "value_template": cond.get("value_template", "{{ true }}"),
            })

    # Build action dict
    action_service = args.get("action_service", "")
    action_entity = args.get("action_entity", "")
    if not action_service or not action_entity:
        return {"error": "action_service and action_entity are required"}

    action = {"service": action_service, "target": {"entity_id": action_entity}}
    if args.get("action_data"):
        action["data"] = args["action_data"]

    # Post directly to HA Supervisor API (structured, no regex needed)
    ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")

    if not ha_token:
        return {"error": "No SUPERVISOR_TOKEN -- cannot create automations outside HA add-on"}

    import uuid
    automation_id = f"styx_{uuid.uuid4().hex[:12]}"
    config = {
        "id": automation_id,
        "alias": alias,
        "description": f"Created by PilotSuite Styx via conversation.",
        "trigger": [trigger],
        "action": [action],
        "mode": "single",
        "tags": ["pilotsuite_styx"],
    }
    if conditions:
        config["condition"] = conditions

    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
    try:
        resp = http_requests.post(
            f"{ha_url}/config/automation/config/{automation_id}",
            json=config, headers=headers, timeout=15,
        )
        if resp.ok:
            # Also record in AutomationCreator if available
            if creator:
                try:
                    creator._created.append({
                        "automation_id": automation_id,
                        "alias": alias,
                        "created_at": time.time(),
                        "antecedent": json.dumps(trigger),
                        "consequent": json.dumps(action),
                    })
                except Exception:
                    pass

            logger.info("Automation created via conversation: %s (%s)", automation_id, alias)
            return {
                "success": True,
                "automation_id": automation_id,
                "alias": alias,
                "message": f"Automation '{alias}' erfolgreich erstellt!",
            }
        else:
            return {"error": f"HA API error ({resp.status_code}): {resp.text[:200]}"}
    except Exception as exc:
        return {"error": f"Failed to create automation: {exc}"}


def _execute_list_automations() -> dict:
    """List automations created by PilotSuite."""
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        creator = services.get("automation_creator")
        if creator:
            items = creator.list_created()
            return {"automations": items, "count": len(items)}
    except Exception:
        pass
    return {"automations": [], "count": 0, "message": "AutomationCreator not available"}


def _execute_web_search(args: dict) -> dict:
    """Search the web via WebSearchService."""
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        ws = services.get("web_search_service")
        if ws:
            query = args.get("query", "")
            max_results = min(int(args.get("max_results", 5)), 10)
            return ws.search(query, max_results=max_results)
    except Exception as exc:
        logger.warning("Web search failed: %s", exc)
    return {"error": "WebSearchService not available", "results": []}


def _execute_get_news(args: dict) -> dict:
    """Get current news headlines."""
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        ws = services.get("web_search_service")
        if ws:
            max_items = min(int(args.get("max_items", 10)), 20)
            return ws.get_news(max_items=max_items)
    except Exception as exc:
        logger.warning("News fetch failed: %s", exc)
    return {"error": "WebSearchService not available", "items": []}


def _execute_get_warnings() -> dict:
    """Get regional warnings (NINA + DWD)."""
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        ws = services.get("web_search_service")
        if ws:
            return ws.get_regional_warnings()
    except Exception as exc:
        logger.warning("Warning fetch failed: %s", exc)
    return {"error": "WebSearchService not available", "warnings": []}


def _execute_play_zone(args: dict) -> dict:
    """Control media playback in a habitus zone."""
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        mgr = services.get("media_zone_manager")
        if not mgr:
            return {"error": "MediaZoneManager not available"}

        zone_id = args.get("zone_id", "")
        action = args.get("action", "play")

        if action == "play":
            return mgr.play_zone(zone_id)
        elif action == "pause":
            return mgr.pause_zone(zone_id)
        elif action == "volume":
            vol = float(args.get("volume", 0.5))
            return mgr.set_zone_volume(zone_id, vol)
        elif action == "play_media":
            return mgr.play_media_in_zone(
                zone_id,
                args.get("media_content_id", ""),
                args.get("media_content_type", "music"),
            )
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as exc:
        logger.warning("Zone media control failed: %s", exc)
        return {"error": str(exc)}


def _execute_musikwolke(args: dict) -> dict:
    """Control Musikwolke (smart audio follow) sessions."""
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        mgr = services.get("media_zone_manager")
        if not mgr:
            return {"error": "MediaZoneManager not available"}

        action = args.get("action", "status")

        if action == "start":
            person_id = args.get("person_id", "")
            source_zone = args.get("source_zone", "")
            if not person_id or not source_zone:
                return {"error": "person_id and source_zone are required for start"}
            return mgr.start_musikwolke(person_id, source_zone)
        elif action == "stop":
            session_id = args.get("session_id", "")
            if not session_id:
                return {"error": "session_id is required for stop"}
            return mgr.stop_musikwolke(session_id)
        elif action == "status":
            sessions = mgr.get_musikwolke_sessions()
            return {"ok": True, "sessions": sessions, "count": len(sessions)}
        else:
            return {"error": f"Unknown action: {action}"}
    except Exception as exc:
        logger.warning("Musikwolke control failed: %s", exc)
        return {"error": str(exc)}


def _execute_waste_status() -> dict:
    """Get waste collection status."""
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        ws = services.get("waste_service")
        if ws:
            return ws.get_status()
    except Exception as exc:
        logger.warning("Waste status failed: %s", exc)
    return {"error": "WasteCollectionService not available", "collections": []}


def _execute_birthday_status() -> dict:
    """Get birthday status."""
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        bs = services.get("birthday_service")
        if bs:
            return bs.get_status()
    except Exception as exc:
        logger.warning("Birthday status failed: %s", exc)
    return {"error": "BirthdayService not available", "today": [], "upcoming": []}


def _execute_save_scene(args: dict) -> dict:
    """Save current zone conditions as a scene."""
    try:
        from copilot_core.api.v1.scenes import _scene_cache
        import uuid

        zone_id = args.get("zone_id", "")
        zone_name = args.get("zone_name", zone_id)
        scene_name = args.get("name")
        entity_ids = args.get("entity_ids", [])

        if not zone_id or not entity_ids:
            return {"error": "zone_id and entity_ids are required"}

        ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
        ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not ha_token:
            return {"error": "No SUPERVISOR_TOKEN"}

        headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
        capturable = {"light", "switch", "cover", "climate", "fan", "media_player"}

        entity_states = {}
        for eid in entity_ids:
            domain = eid.split(".", 1)[0]
            if domain not in capturable:
                continue
            try:
                resp = http_requests.get(f"{ha_url}/states/{eid}", headers=headers, timeout=5)
                if resp.ok:
                    sd = resp.json()
                    entity_states[eid] = {"state": sd.get("state", "unknown")}
                    attrs = sd.get("attributes", {})
                    for k in ("brightness", "color_temp_kelvin", "current_position", "temperature", "hvac_mode"):
                        if k in attrs:
                            entity_states[eid][k] = attrs[k]
            except Exception:
                pass

        if not entity_states:
            return {"error": "Keine steuerbaren Entitaeten gefunden"}

        scene_id = f"zone_scene_{uuid.uuid4().hex[:12]}"
        name = scene_name or f"{zone_name} — {time.strftime('%d.%m %H:%M')}"

        scene = {
            "scene_id": scene_id,
            "zone_id": zone_id,
            "zone_name": zone_name,
            "name": name,
            "entity_states": entity_states,
            "created_at": time.time(),
            "applied_count": 0,
            "source": "conversation",
        }
        _scene_cache[scene_id] = scene

        # Auto-tag entities with Styx
        _auto_tag_styx_entities("ha.call_service", {"service_data": {"entity_id": list(entity_states.keys())}})

        return {
            "success": True,
            "scene_id": scene_id,
            "name": name,
            "entities_captured": len(entity_states),
            "message": f"Szene '{name}' mit {len(entity_states)} Entitaeten gespeichert!",
        }
    except Exception as exc:
        logger.warning("Save scene failed: %s", exc)
        return {"error": str(exc)}


def _execute_apply_scene(args: dict) -> dict:
    """Apply a saved scene."""
    try:
        from copilot_core.api.v1.scenes import _scene_cache, _apply_entity_state

        scene_id = args.get("scene_id", "")
        if not scene_id:
            # Try by name
            name = args.get("name", "").lower()
            for sid, s in _scene_cache.items():
                if name in s.get("name", "").lower():
                    scene_id = sid
                    break

        scene = _scene_cache.get(scene_id)
        if not scene:
            available = [s.get("name", "?") for s in _scene_cache.values()]
            return {"error": f"Szene nicht gefunden. Verfuegbar: {', '.join(available[:5])}"}

        ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
        ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not ha_token:
            return {"error": "No SUPERVISOR_TOKEN"}

        headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
        for eid, state_data in scene.get("entity_states", {}).items():
            try:
                _apply_entity_state(ha_url, headers, eid, state_data)
            except Exception:
                pass

        scene["applied_count"] = scene.get("applied_count", 0) + 1
        scene["last_applied"] = time.time()
        return {
            "success": True,
            "scene": scene.get("name", scene_id),
            "entities_applied": len(scene.get("entity_states", {})),
            "message": f"Szene '{scene.get('name', scene_id)}' angewendet!",
        }
    except Exception as exc:
        logger.warning("Apply scene failed: %s", exc)
        return {"error": str(exc)}


def _execute_calendar_events(args: dict) -> dict:
    """Get calendar events from HA."""
    try:
        from copilot_core.api.v1.calendar import _fetch_events, _fetch_calendar_entities
        from datetime import datetime, timedelta

        days = min(int(args.get("days", 1)), 30)
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0).isoformat()
        end = (now.replace(hour=0, minute=0, second=0) + timedelta(days=days)).isoformat()

        events = _fetch_events(start, end)
        calendars = _fetch_calendar_entities()

        formatted = []
        for ev in events[:20]:
            ev_start = ev.get("start", {})
            start_str = ev_start.get("dateTime", ev_start.get("date", "?"))
            formatted.append({
                "summary": ev.get("summary", "?"),
                "start": start_str,
                "calendar": ev.get("calendar_entity_id", "?"),
            })

        return {
            "events": formatted,
            "count": len(formatted),
            "calendars": len(calendars),
            "days_queried": days,
        }
    except Exception as exc:
        logger.warning("Calendar events failed: %s", exc)
        return {"error": str(exc), "events": []}


def _execute_shopping_list(args: dict) -> dict:
    """Manage shopping list items."""
    try:
        from copilot_core.api.v1.shopping import _get_conn, _lock
        action = args.get("action", "list")

        if action == "list":
            with _lock:
                conn = _get_conn()
                try:
                    rows = conn.execute(
                        "SELECT id, name, quantity, category FROM shopping_items "
                        "WHERE completed = 0 ORDER BY created_at DESC LIMIT 30"
                    ).fetchall()
                    items = [dict(r) for r in rows]
                    return {"items": items, "count": len(items)}
                finally:
                    conn.close()

        elif action == "add":
            import uuid as _uuid
            items_to_add = args.get("items", [])
            if not items_to_add:
                name = args.get("name", "").strip()
                if not name:
                    return {"error": "name is required"}
                items_to_add = [{"name": name, "quantity": args.get("quantity", "")}]

            added = []
            with _lock:
                conn = _get_conn()
                try:
                    for item in items_to_add:
                        n = item.get("name", "").strip()
                        if not n:
                            continue
                        item_id = f"shop_{_uuid.uuid4().hex[:8]}"
                        conn.execute(
                            "INSERT INTO shopping_items (id, name, quantity, category, created_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (item_id, n, item.get("quantity", ""), item.get("category", ""), time.time()),
                        )
                        added.append(n)
                    conn.commit()
                    return {"success": True, "added": added, "message": f"{len(added)} Artikel hinzugefuegt"}
                finally:
                    conn.close()

        elif action == "complete":
            item_id = args.get("item_id", "")
            if not item_id:
                return {"error": "item_id is required"}
            with _lock:
                conn = _get_conn()
                try:
                    cursor = conn.execute(
                        "UPDATE shopping_items SET completed = 1, completed_at = ? WHERE id = ?",
                        (time.time(), item_id),
                    )
                    conn.commit()
                    return {"success": cursor.rowcount > 0}
                finally:
                    conn.close()

        elif action == "clear_completed":
            with _lock:
                conn = _get_conn()
                try:
                    cursor = conn.execute("DELETE FROM shopping_items WHERE completed = 1")
                    conn.commit()
                    return {"success": True, "deleted": cursor.rowcount}
                finally:
                    conn.close()

        return {"error": f"Unknown action: {action}"}
    except Exception as exc:
        logger.warning("Shopping list failed: %s", exc)
        return {"error": str(exc)}


def _execute_reminder(args: dict) -> dict:
    """Manage reminders."""
    try:
        from copilot_core.api.v1.shopping import _get_conn, _lock
        action = args.get("action", "list")

        if action == "list":
            with _lock:
                conn = _get_conn()
                try:
                    rows = conn.execute(
                        "SELECT id, title, description, due_at, recurring FROM reminders "
                        "WHERE completed = 0 ORDER BY due_at ASC NULLS LAST LIMIT 20"
                    ).fetchall()
                    items = [dict(r) for r in rows]
                    return {"reminders": items, "count": len(items)}
                finally:
                    conn.close()

        elif action == "add":
            import uuid as _uuid
            title = args.get("title", "").strip()
            if not title:
                return {"error": "title is required"}

            due_at = args.get("due_at")
            if isinstance(due_at, str):
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
                    due_at = dt.timestamp()
                except (ValueError, TypeError):
                    due_at = None

            rem_id = f"rem_{_uuid.uuid4().hex[:8]}"
            with _lock:
                conn = _get_conn()
                try:
                    conn.execute(
                        "INSERT INTO reminders (id, title, description, due_at, recurring, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (rem_id, title, args.get("description", ""), due_at,
                         args.get("recurring", ""), time.time()),
                    )
                    conn.commit()
                    return {"success": True, "id": rem_id, "title": title,
                            "message": f"Erinnerung '{title}' erstellt!"}
                finally:
                    conn.close()

        elif action == "complete":
            rem_id = args.get("reminder_id", "")
            if not rem_id:
                return {"error": "reminder_id is required"}
            with _lock:
                conn = _get_conn()
                try:
                    cursor = conn.execute(
                        "UPDATE reminders SET completed = 1, completed_at = ? WHERE id = ?",
                        (time.time(), rem_id),
                    )
                    conn.commit()
                    return {"success": cursor.rowcount > 0}
                finally:
                    conn.close()

        elif action == "snooze":
            rem_id = args.get("reminder_id", "")
            minutes = int(args.get("snooze_minutes", 30))
            if not rem_id:
                return {"error": "reminder_id is required"}
            with _lock:
                conn = _get_conn()
                try:
                    conn.execute(
                        "UPDATE reminders SET snoozed_until = ? WHERE id = ? AND completed = 0",
                        (time.time() + minutes * 60, rem_id),
                    )
                    conn.commit()
                    return {"success": True, "snoozed_minutes": minutes}
                finally:
                    conn.close()

        return {"error": f"Unknown action: {action}"}
    except Exception as exc:
        logger.warning("Reminder failed: %s", exc)
        return {"error": str(exc)}


def _auto_tag_styx_entities(tool_name: str, tool_args: dict) -> None:
    """Auto-tag entities Styx interacted with via the 'Styx' tag.

    Fire-and-forget: posts entity_ids to the HACS integration's tag endpoint.
    The HACS EntityTagsModule handles persistence.
    """
    entity_ids = []
    try:
        # Extract entity IDs from tool call arguments
        if tool_name == "ha.call_service":
            target = tool_args.get("target", {})
            if isinstance(target, dict):
                eid = target.get("entity_id")
                if isinstance(eid, str):
                    entity_ids.append(eid)
                elif isinstance(eid, list):
                    entity_ids.extend(eid)
            # Also check service_data for entity_id
            sdata = tool_args.get("service_data", {})
            if isinstance(sdata, dict) and "entity_id" in sdata:
                eid = sdata["entity_id"]
                if isinstance(eid, str):
                    entity_ids.append(eid)
                elif isinstance(eid, list):
                    entity_ids.extend(eid)
        elif tool_name in ("ha.get_states", "ha.activate_scene"):
            eid = tool_args.get("entity_id", "")
            if eid:
                entity_ids.append(eid)
        elif tool_name == "ha.get_history":
            eids = tool_args.get("entity_ids", [])
            entity_ids.extend(eids)
        elif tool_name == "pilotsuite.play_zone":
            # Zone interactions don't have direct entity IDs
            pass
        elif tool_name == "pilotsuite.create_automation":
            eid = tool_args.get("trigger_entity", "")
            if eid:
                entity_ids.append(eid)
            eid = tool_args.get("action_entity", "")
            if eid:
                entity_ids.append(eid)

        if not entity_ids:
            return

        # Post to HACS integration via Core addon's internal tag sync
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        tag_registry = services.get("tag_registry")
        if tag_registry and hasattr(tag_registry, "auto_tag_styx"):
            tag_registry.auto_tag_styx(entity_ids)
        else:
            # Store for batch sync to HACS
            styx_queue = current_app.config.setdefault("STYX_TAG_QUEUE", [])
            styx_queue.extend(entity_ids)
            logger.debug("Queued %d entities for Styx auto-tagging", len(entity_ids))

    except Exception:
        logger.debug("Auto Styx tagging failed (non-critical)", exc_info=True)


def process_with_tool_execution(user_message: str) -> str:
    """Process a message with server-side tool execution.

    Used by Telegram bot and direct chat.  Handles the full tool-calling loop:
    LLM -> tool_calls -> execute via HA REST API -> feed results -> repeat.
    """
    messages = [{"role": "user", "content": user_message}]
    tools = _get_mcp_tools().get("functions", []) or None

    for _ in range(MAX_TOOL_ROUNDS):
        response = _process_conversation(messages, tools=tools)
        choice = response.get("choices", [{}])[0]
        msg = choice.get("message", {})

        if choice.get("finish_reason") != "tool_calls" or not msg.get("tool_calls"):
            return msg.get("content", "")

        # Append assistant message (with tool_calls) to conversation
        messages.append(msg)

        # Execute each tool and append results
        for tc in msg["tool_calls"]:
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            try:
                tool_args = json.loads(fn.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                tool_args = {}

            result = _execute_ha_tool(tool_name, tool_args)

            # Auto-tag Styx-interacted entities (v3.4.0)
            _auto_tag_styx_entities(tool_name, tool_args)

            messages.append({
                "role": "tool",
                "content": json.dumps(result, default=str),
                "tool_call_id": tc.get("id", ""),
            })

    return msg.get("content", "") or "Maximale Tool-Runden erreicht."


def _stream_response(response: dict):
    """OpenAI-compatible SSE streaming implementation."""
    model = response.get("model", DEFAULT_MODEL)
    response_id = response.get("id", f"chatcmpl-{os.urandom(12).hex()}")

    def generate():
        content = response["choices"][0]["message"]["content"]
        # Stream word by word for natural feel
        words = content.split()
        for i, word in enumerate(words):
            chunk = {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": word + (" " if i < len(words) - 1 else "")},
                    "finish_reason": None,
                }],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

        # Final chunk with finish_reason
        final = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(final)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype='text/event-stream',
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def register_routes(app):
    """Register conversation routes with Flask app."""
    app.register_blueprint(conversation_bp)
    app.register_blueprint(openai_compat_bp)
    logger.info("Registered conversation API at /chat/* and /v1/*")
