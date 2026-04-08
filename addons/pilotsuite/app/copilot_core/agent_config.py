"""Styx Agent Auto-Config & Health Check (v5.21.0).

Provides endpoints to verify agent connectivity, report status,
and configure agent personality for the HA conversation integration.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

agent_config_bp = Blueprint("agent_config", __name__, url_prefix="/api/v1/agent")

# ── Data classes ─────────────────────────────────────────────────────────


@dataclass
class AgentStatus:
    """Styx agent health and status."""

    agent_name: str
    agent_version: str
    status: str  # "ready", "degraded", "offline"
    uptime_seconds: float
    conversation_ready: bool
    llm_available: bool
    llm_model: str
    llm_backend: str  # "ollama", "cloud", "none"
    supported_languages: list[str]
    character: str
    features: list[str]
    last_health_check: str


@dataclass
class AgentCapabilities:
    """What the agent can do."""

    conversation: bool
    tool_calling: bool
    web_search: bool
    automation_creation: bool
    energy_management: bool
    mood_tracking: bool
    brain_graph: bool
    regional_context: bool
    proactive_alerts: bool
    multilingual: bool
    characters: list[str]


@dataclass
class AgentGreeting:
    """Greeting message for new installations."""

    language: str
    greeting: str
    introduction: str
    capabilities_summary: str
    setup_hints: list[str]


# ── Module state ─────────────────────────────────────────────────────────

_start_time: float = time.time()
_config: dict = {}
_llm_provider = None
_conversation_module = None
_model_pull_lock = threading.Lock()
_model_pull_inflight: set[str] = set()


def init_agent_config(
    config: dict | None = None,
    llm_provider=None,
    conversation_module=None,
) -> None:
    """Initialize agent config module."""
    global _config, _llm_provider, _conversation_module, _start_time
    _config = config or {}
    _llm_provider = llm_provider
    _conversation_module = conversation_module
    _start_time = time.time()
    logger.info("Agent config module initialized")


def _as_bool(value: object, default: bool) -> bool:
    """Parse bool-like values from options/env."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return default


def _conversation_config() -> dict:
    """Return normalized conversation config (nested + flat + env fallbacks)."""
    conv = dict(_config.get("conversation", {}) or {})

    flat_map = {
        "ollama_url": "conversation_ollama_url",
        "ollama_model": "conversation_ollama_model",
        "cloud_api_url": "conversation_cloud_api_url",
        "cloud_api_key": "conversation_cloud_api_key",
        "cloud_model": "conversation_cloud_model",
        "assistant_name": "conversation_assistant_name",
        "character": "conversation_character",
    }
    for conv_key, flat_key in flat_map.items():
        if conv.get(conv_key) not in (None, ""):
            continue
        value = _config.get(flat_key)
        if value not in (None, ""):
            conv[conv_key] = value

    if "prefer_local" not in conv:
        conv["prefer_local"] = _config.get("conversation_prefer_local", True)
    if "enabled" not in conv:
        conv["enabled"] = _config.get("conversation_enabled", True)

    env_map = {
        "ollama_url": "OLLAMA_URL",
        "ollama_model": "OLLAMA_MODEL",
        "cloud_api_url": "CLOUD_API_URL",
        "cloud_api_key": "CLOUD_API_KEY",
        "cloud_model": "CLOUD_MODEL",
        "assistant_name": "ASSISTANT_NAME",
        "character": "CONVERSATION_CHARACTER",
    }
    for conv_key, env_key in env_map.items():
        if conv.get(conv_key) not in (None, ""):
            continue
        env_value = os.environ.get(env_key, "").strip()
        if env_value:
            conv[conv_key] = env_value

    conv.setdefault("ollama_url", "http://localhost:11434")
    conv.setdefault("ollama_model", "qwen3:0.6b")
    conv.setdefault("assistant_name", "Styx")
    conv.setdefault("character", "copilot")
    conv["prefer_local"] = _as_bool(conv.get("prefer_local"), True)
    conv["enabled"] = _as_bool(conv.get("enabled"), True)
    return conv


def _get_llm_provider_instance():
    """Return LLM provider instance (shared when available)."""
    provider = _llm_provider
    if provider is not None:
        return provider
    try:
        from copilot_core.llm_provider import LLMProvider
        provider = LLMProvider()
    except Exception:
        return None
    return provider


def _ollama_installed_models(ollama_url: str) -> list[str]:
    """Fetch installed Ollama models (best effort)."""
    try:
        import requests as http_requests

        resp = http_requests.get(f"{ollama_url}/api/tags", timeout=5)
        if resp.status_code != 200:
            return []
        return [str(model.get("name", "")).strip() for model in resp.json().get("models", []) if model.get("name")]
    except Exception:
        return []


def _spawn_model_pull(model: str) -> dict[str, str]:
    """Start non-blocking `ollama pull <model>` when possible."""
    normalized = str(model or "").strip()
    if not normalized:
        return {"status": "skipped", "reason": "no_model"}

    if shutil.which("ollama") is None:
        return {"status": "skipped", "reason": "ollama_binary_missing"}

    with _model_pull_lock:
        if normalized in _model_pull_inflight:
            return {"status": "already_running", "model": normalized}
        _model_pull_inflight.add(normalized)

    def _run() -> None:
        try:
            subprocess.run(
                ["ollama", "pull", normalized],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        finally:
            with _model_pull_lock:
                _model_pull_inflight.discard(normalized)

    thread = threading.Thread(target=_run, name=f"ollama_pull_{normalized}", daemon=True)
    thread.start()
    return {"status": "started", "model": normalized}


def _get_agent_version() -> str:
    """Get current agent version from config."""
    version = str(_config.get("version", "") or "").strip()
    if version:
        return version
    env_version = str(os.environ.get("COPILOT_VERSION", "") or os.environ.get("BUILD_VERSION", "")).strip()
    if env_version:
        return env_version
    return "5.21.0"


def _check_llm_available() -> tuple[bool, str, str]:
    """Check if LLM backend is available."""
    conv_config = _conversation_config()
    provider = _get_llm_provider_instance()
    if provider is not None:
        try:
            if hasattr(provider, "reload_config"):
                provider.reload_config()
            status = provider.status()
            active_provider = str(status.get("active_provider", "none"))
            if active_provider == "ollama":
                return True, str(status.get("ollama_model", "")), "ollama"
            if active_provider == "cloud":
                return True, str(status.get("cloud_model", "")), "cloud"
            if bool(status.get("cloud_configured")):
                return True, str(status.get("cloud_model", "")), "cloud"
        except Exception:
            logger.exception("Could not query LLM provider status")

    prefer_local = _as_bool(conv_config.get("prefer_local"), True)
    if prefer_local:
        model = str(conv_config.get("ollama_model", "qwen3:0.6b"))
        return True, model, "ollama"

    cloud_url = str(conv_config.get("cloud_api_url", "") or "").strip()
    cloud_model = str(conv_config.get("cloud_model", "") or "").strip()
    if cloud_url and cloud_model:
        return True, cloud_model, "cloud"
    return False, "", "none"


def _get_features() -> list[str]:
    """List enabled features."""
    features = ["conversation"]

    conv = _config.get("conversation", {})
    if conv.get("enabled", True):
        features.append("chat_completions")

    if _config.get("openai_api", {}).get("enabled", True):
        features.append("openai_compatible_api")

    if _config.get("brain_graph", {}).get("max_nodes", 0) > 0:
        features.append("brain_graph")

    if _config.get("knowledge_graph", {}).get("enabled", False):
        features.append("knowledge_graph")

    if _config.get("user_preferences", {}).get("enabled", False):
        features.append("user_preferences")

    if _config.get("telegram", {}).get("enabled", False):
        features.append("telegram")

    if _config.get("web_search", {}).get("ags_code"):
        features.append("regional_news")

    features.append("regional_context")
    features.append("energy_forecast")
    features.append("proactive_alerts")

    return features


def _get_character() -> str:
    """Get active character preset."""
    return str(_conversation_config().get("character", "copilot"))


# ── Greeting templates ───────────────────────────────────────────────────

_GREETINGS = {
    "de": AgentGreeting(
        language="de",
        greeting="Hallo! Ich bin Styx, dein lokaler KI-Assistent von PilotSuite.",
        introduction=(
            "Ich laufe vollstaendig lokal auf deinem Home Assistant — "
            "keine Cloud, keine Daten die dein Zuhause verlassen. "
            "Ich kann dir bei der Steuerung deines Smart Homes helfen, "
            "Energieoptimierung durchfuehren, Automationen erstellen "
            "und vieles mehr."
        ),
        capabilities_summary=(
            "Meine Faehigkeiten: Gespraeche fuehren, Geraete steuern, "
            "Energieprognosen erstellen, Wetterwarnungen auswerten, "
            "Strompreise optimieren, Stimmung und Gewohnheiten lernen."
        ),
        setup_hints=[
            "Oeffne Einstellungen > Sprachassistenten und waehle PilotSuite als Gesprächsagent",
            "Nutze das PilotSuite Dashboard fuer Stimmung, Neuronen und Habitus",
            "Konfiguriere Habitus-Zonen unter Einstellungen > Integrationen > PilotSuite",
            "Alle Verarbeitung laeuft lokal — keine Cloud erforderlich",
        ],
    ),
    "en": AgentGreeting(
        language="en",
        greeting="Hello! I'm Styx, your local AI assistant from PilotSuite.",
        introduction=(
            "I run entirely locally on your Home Assistant — "
            "no cloud, no data leaving your home. "
            "I can help you control your smart home, "
            "optimize energy usage, create automations, "
            "and much more."
        ),
        capabilities_summary=(
            "My capabilities: conversations, device control, "
            "energy forecasts, weather warnings, electricity price optimization, "
            "mood tracking, and habit learning."
        ),
        setup_hints=[
            "Open Settings > Voice Assistants and select PilotSuite as conversation agent",
            "Use the PilotSuite dashboard for Mood, Neurons, and Habitus cards",
            "Configure Habitus zones via Settings > Integrations > PilotSuite",
            "All processing runs locally — no cloud required",
        ],
    ),
}


# ── API endpoints ────────────────────────────────────────────────────────


@agent_config_bp.route("/status", methods=["GET"])
@require_token
def get_agent_status():
    """Get Styx agent health status."""
    llm_available, llm_model, llm_backend = _check_llm_available()
    conv_config = _conversation_config()

    status = AgentStatus(
        agent_name=str(conv_config.get("assistant_name", "Styx")),
        agent_version=_get_agent_version(),
        status="ready" if llm_available else "degraded",
        uptime_seconds=round(time.time() - _start_time, 1),
        conversation_ready=True,
        llm_available=llm_available,
        llm_model=llm_model,
        llm_backend=llm_backend,
        supported_languages=["de", "en"],
        character=_get_character(),
        features=_get_features(),
        last_health_check=datetime.now().isoformat(),
    )
    return jsonify({"ok": True, **asdict(status)})


@agent_config_bp.route("/capabilities", methods=["GET"])
@require_token
def get_agent_capabilities():
    """Get what the agent can do."""
    features = _get_features()

    caps = AgentCapabilities(
        conversation=True,
        tool_calling="chat_completions" in features,
        web_search="regional_news" in features,
        automation_creation=True,
        energy_management="energy_forecast" in features,
        mood_tracking="brain_graph" in features,
        brain_graph="brain_graph" in features,
        regional_context="regional_context" in features,
        proactive_alerts="proactive_alerts" in features,
        multilingual=True,
        characters=["copilot", "butler", "energy_manager", "security_guard", "friendly", "minimal"],
    )
    return jsonify({"ok": True, **asdict(caps)})


@agent_config_bp.route("/greeting", methods=["GET"])
@require_token
def get_greeting():
    """Get installation greeting message."""
    lang = request.args.get("lang", "de")
    greeting = _GREETINGS.get(lang, _GREETINGS["en"])
    return jsonify({"ok": True, **asdict(greeting)})


@agent_config_bp.route("/ping", methods=["GET"])
@require_token
def agent_ping():
    """Simple ping to verify agent is alive — for bidirectional check."""
    conv_config = _conversation_config()
    return jsonify({
        "ok": True,
        "pong": True,
        "agent": str(conv_config.get("assistant_name", "Styx")),
        "timestamp": datetime.now().isoformat(),
    })


@agent_config_bp.route("/verify", methods=["POST"])
@require_token
def verify_bidirectional():
    """Verify bidirectional communication (HA sends, Core responds with echo + status).

    JSON body: {"message": "hello", "source": "ha_integration"}
    """
    body = request.get_json(silent=True) or {}
    message = body.get("message", "")
    source = body.get("source", "unknown")

    llm_available, llm_model, llm_backend = _check_llm_available()

    conv_config = _conversation_config()
    return jsonify({
        "ok": True,
        "echo": message,
        "source_received": source,
        "agent_name": str(conv_config.get("assistant_name", "Styx")),
        "agent_ready": True,
        "llm_available": llm_available,
        "llm_model": llm_model,
        "features": _get_features(),
        "timestamp": datetime.now().isoformat(),
    })


@agent_config_bp.route("/self-heal", methods=["POST"])
@require_token
def self_heal_agent():
    """Best-effort self-heal for LLM availability after setup/updates."""
    body = request.get_json(silent=True) or {}
    reason = str(body.get("reason", "manual")).strip() or "manual"

    conv_config = _conversation_config()
    steps: list[dict] = []
    provider_status: dict = {}

    provider = _get_llm_provider_instance()
    if provider is not None and hasattr(provider, "reload_config"):
        try:
            provider.reload_config()
            steps.append({"step": "reload_provider_config", "ok": True})
        except Exception as exc:
            steps.append({"step": "reload_provider_config", "ok": False, "error": str(exc)})

    if provider is not None:
        try:
            provider_status = provider.status()
            steps.append({"step": "provider_status", "ok": True})
        except Exception as exc:
            steps.append({"step": "provider_status", "ok": False, "error": str(exc)})
            provider_status = {}

    ollama_url = str(provider_status.get("ollama_url") or conv_config.get("ollama_url") or "http://localhost:11434")
    model = str(provider_status.get("ollama_model") or conv_config.get("ollama_model") or "qwen3:0.6b")
    fallback_model = "qwen3:0.6b"

    installed_models = _ollama_installed_models(ollama_url)
    if installed_models:
        steps.append(
            {
                "step": "list_installed_models",
                "ok": True,
                "count": len(installed_models),
            }
        )
    else:
        steps.append({"step": "list_installed_models", "ok": False, "count": 0})

    pulls: list[dict[str, str]] = []
    if _as_bool(conv_config.get("prefer_local"), True):
        model_names = {name.split(":")[0] for name in installed_models}
        full_names = set(installed_models)

        def _model_missing(target: str) -> bool:
            base = target.split(":")[0]
            return target not in full_names and base not in model_names

        if _model_missing(fallback_model):
            pulls.append(_spawn_model_pull(fallback_model))
        if _model_missing(model):
            pulls.append(_spawn_model_pull(model))

    for pull in pulls:
        steps.append({"step": "pull_model", **pull})

    llm_available, llm_model, llm_backend = _check_llm_available()
    return jsonify(
        {
            "ok": True,
            "reason": reason,
            "agent_name": str(conv_config.get("assistant_name", "Styx")),
            "llm_available": llm_available,
            "llm_model": llm_model,
            "llm_backend": llm_backend,
            "provider_status": provider_status,
            "installed_models": installed_models,
            "steps": steps,
            "timestamp": datetime.now().isoformat(),
        }
    )
