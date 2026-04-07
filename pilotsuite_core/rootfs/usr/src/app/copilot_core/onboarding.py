"""Styx Onboarding & Greeting Flow (v5.22.0).

Welcome flow for new installations — Styx introduces itself,
explains capabilities, walks through initial configuration,
and verifies the setup is working.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

onboarding_bp = Blueprint("onboarding", __name__, url_prefix="/api/v1/onboarding")


# ── Data classes ─────────────────────────────────────────────────────────


@dataclass
class OnboardingStep:
    """Single onboarding step."""

    step_id: str
    order: int
    title_de: str
    title_en: str
    description_de: str
    description_en: str
    icon: str
    action: str  # "info", "configure", "verify", "done"
    completed: bool = False
    skipped: bool = False
    data: dict = field(default_factory=dict)


@dataclass
class OnboardingState:
    """Complete onboarding state."""

    started_at: str
    completed_at: str
    current_step: int
    total_steps: int
    steps: list[dict]
    is_complete: bool
    agent_name: str
    language: str


@dataclass
class WelcomeMessage:
    """Welcome message from Styx."""

    language: str
    agent_name: str
    greeting: str
    message: str
    personality: str
    quick_actions: list[dict]


# ── Module state ─────────────────────────────────────────────────────────

_config: dict = {}
_onboarding_state: dict = {}
_start_time: float = 0


def init_onboarding(config: dict | None = None) -> None:
    """Initialize onboarding module."""
    global _config, _start_time
    _config = config or {}
    _start_time = time.time()
    logger.info("Onboarding module initialized")


def _get_agent_name() -> str:
    return _config.get("conversation", {}).get("assistant_name", "Styx")


def _get_language() -> str:
    """Detect language from config."""
    # German by default for DACH region
    return "de"


# ── Onboarding Steps ────────────────────────────────────────────────────

_STEPS_DE = [
    OnboardingStep(
        step_id="welcome",
        order=0,
        title_de="Willkommen bei PilotSuite",
        title_en="Welcome to PilotSuite",
        description_de=(
            "Hallo! Ich bin Styx, dein lokaler KI-Assistent. "
            "Ich laufe vollstaendig auf deinem Home Assistant — "
            "keine Cloud, keine externen Server. Lass uns loslegen!"
        ),
        description_en=(
            "Hello! I'm Styx, your local AI assistant. "
            "I run entirely on your Home Assistant — "
            "no cloud, no external servers. Let's get started!"
        ),
        icon="mdi:hand-wave",
        action="info",
    ),
    OnboardingStep(
        step_id="llm_check",
        order=1,
        title_de="KI-Modell pruefen",
        title_en="Check AI Model",
        description_de=(
            "Ich pruefe ob dein lokales KI-Modell (Ollama) erreichbar ist. "
            "Das Modell ist mein Gehirn — damit fuehre ich Gespraeche und verstehe Anfragen."
        ),
        description_en=(
            "Checking if your local AI model (Ollama) is reachable. "
            "The model is my brain — I use it for conversations and understanding requests."
        ),
        icon="mdi:brain",
        action="verify",
    ),
    OnboardingStep(
        step_id="conversation_agent",
        order=2,
        title_de="Gesprächsagent einrichten",
        title_en="Set Up Conversation Agent",
        description_de=(
            "Styx wurde als Gesprächsagent in Home Assistant registriert. "
            "Gehe zu Einstellungen > Sprachassistenten und waehle PilotSuite "
            "als Standard-Agent fuer Sprachsteuerung."
        ),
        description_en=(
            "Styx has been registered as a conversation agent in Home Assistant. "
            "Go to Settings > Voice Assistants and select PilotSuite "
            "as the default agent for voice control."
        ),
        icon="mdi:microphone",
        action="configure",
    ),
    OnboardingStep(
        step_id="regional_config",
        order=3,
        title_de="Region konfigurieren",
        title_en="Configure Region",
        description_de=(
            "Dein Standort wird automatisch aus Home Assistant uebernommen. "
            "Damit erhaeltst du lokale Wetterwarnungen, Strompreise, "
            "Solarprognosen und Kraftstoffpreise."
        ),
        description_en=(
            "Your location is automatically detected from Home Assistant. "
            "This enables local weather warnings, electricity prices, "
            "solar forecasts, and fuel prices."
        ),
        icon="mdi:map-marker",
        action="configure",
    ),
    OnboardingStep(
        step_id="energy_setup",
        order=4,
        title_de="Energie-Optimierung",
        title_en="Energy Optimization",
        description_de=(
            "PilotSuite optimiert deinen Energieverbrauch automatisch. "
            "Konfiguriere optional: PV-Anlage (kWp), Batteriespeicher, "
            "Stromtarif (dynamisch/fest), und Wallbox."
        ),
        description_en=(
            "PilotSuite automatically optimizes your energy usage. "
            "Optionally configure: PV system (kWp), battery storage, "
            "electricity tariff (dynamic/fixed), and EV charger."
        ),
        icon="mdi:solar-power",
        action="configure",
    ),
    OnboardingStep(
        step_id="dashboard_check",
        order=5,
        title_de="Dashboard pruefen",
        title_en="Check Dashboard",
        description_de=(
            "Das PilotSuite Dashboard wurde automatisch erstellt. "
            "Oeffne es unter Uebersicht > PilotSuite fuer Stimmung, "
            "Neuronen, Energie, und Empfehlungen."
        ),
        description_en=(
            "The PilotSuite dashboard has been automatically created. "
            "Open it under Overview > PilotSuite for mood, "
            "neurons, energy, and recommendations."
        ),
        icon="mdi:view-dashboard",
        action="verify",
    ),
    OnboardingStep(
        step_id="test_conversation",
        order=6,
        title_de="Testgespräch",
        title_en="Test Conversation",
        description_de=(
            "Sag etwas zu Styx! Oeffne den Chat und schreibe z.B.: "
            "'Hallo Styx, was kannst du?' — Ich antworte dir sofort."
        ),
        description_en=(
            "Say something to Styx! Open the chat and type e.g.: "
            "'Hello Styx, what can you do?' — I'll reply right away."
        ),
        icon="mdi:chat",
        action="verify",
    ),
    OnboardingStep(
        step_id="complete",
        order=7,
        title_de="Einrichtung abgeschlossen!",
        title_en="Setup Complete!",
        description_de=(
            "Glueckwunsch! PilotSuite ist bereit. Ich lerne von deinen "
            "Gewohnheiten und werde mit der Zeit immer besser. "
            "Frag mich jederzeit — ich bin hier um zu helfen!"
        ),
        description_en=(
            "Congratulations! PilotSuite is ready. I'll learn from your "
            "habits and get better over time. "
            "Ask me anytime — I'm here to help!"
        ),
        icon="mdi:check-circle",
        action="done",
    ),
]


def _get_onboarding_steps() -> list[OnboardingStep]:
    """Get fresh copy of onboarding steps."""
    return [
        OnboardingStep(
            step_id=s.step_id,
            order=s.order,
            title_de=s.title_de,
            title_en=s.title_en,
            description_de=s.description_de,
            description_en=s.description_en,
            icon=s.icon,
            action=s.action,
        )
        for s in _STEPS_DE
    ]


def get_onboarding_state(session_id: str = "default") -> OnboardingState:
    """Get current onboarding state."""
    state = _onboarding_state.get(session_id)

    if state is None:
        # Initialize new onboarding
        steps = _get_onboarding_steps()
        state = {
            "started_at": datetime.now().isoformat(),
            "completed_at": "",
            "current_step": 0,
            "steps": steps,
        }
        _onboarding_state[session_id] = state

    steps = state["steps"]
    completed = all(s.completed or s.skipped for s in steps)
    current = next(
        (s.order for s in steps if not s.completed and not s.skipped),
        len(steps),
    )

    return OnboardingState(
        started_at=state["started_at"],
        completed_at=state.get("completed_at", ""),
        current_step=current,
        total_steps=len(steps),
        steps=[asdict(s) for s in steps],
        is_complete=completed,
        agent_name=_get_agent_name(),
        language=_get_language(),
    )


def complete_step(session_id: str, step_id: str) -> OnboardingState:
    """Mark an onboarding step as complete."""
    state = _onboarding_state.get(session_id)
    if state is None:
        get_onboarding_state(session_id)
        state = _onboarding_state[session_id]

    for s in state["steps"]:
        if s.step_id == step_id:
            s.completed = True
            break

    # Check if all done
    if all(s.completed or s.skipped for s in state["steps"]):
        state["completed_at"] = datetime.now().isoformat()

    return get_onboarding_state(session_id)


def skip_step(session_id: str, step_id: str) -> OnboardingState:
    """Skip an onboarding step."""
    state = _onboarding_state.get(session_id)
    if state is None:
        get_onboarding_state(session_id)
        state = _onboarding_state[session_id]

    for s in state["steps"]:
        if s.step_id == step_id:
            s.skipped = True
            break

    return get_onboarding_state(session_id)


def get_welcome_message(language: str = "de") -> WelcomeMessage:
    """Get personalized welcome message from Styx."""
    agent = _get_agent_name()
    character = _config.get("conversation", {}).get("character", "copilot")

    if language == "de":
        personalities = {
            "copilot": "Hilfsbereit und proaktiv",
            "butler": "Stilvoll und diskret",
            "energy_manager": "Effizient und datengetrieben",
            "security_guard": "Wachsam und schützend",
            "friendly": "Warm und gesprächig",
            "minimal": "Knapp und direkt",
        }
        greeting = f"Hallo! Ich bin {agent}."
        message = (
            f"Willkommen bei PilotSuite! Ich bin {agent}, dein persoenlicher "
            f"KI-Assistent fuer dein Smart Home. Ich laufe komplett lokal "
            f"auf deinem Home Assistant — deine Daten bleiben bei dir.\n\n"
            f"Ich kann dir helfen bei:\n"
            f"- Geraete steuern und Automationen erstellen\n"
            f"- Energieverbrauch optimieren und Strompreise nutzen\n"
            f"- Wetterwarnungen auswerten und proaktiv reagieren\n"
            f"- Stimmung und Gewohnheiten lernen\n"
            f"- Und vieles mehr!"
        )
        quick_actions = [
            {"label": "Test: Hallo Styx!", "action": "chat", "payload": f"Hallo {agent}, was kannst du?"},
            {"label": "Energiestatus", "action": "chat", "payload": "Wie ist mein aktueller Energiestatus?"},
            {"label": "Dashboard oeffnen", "action": "navigate", "payload": "/pilotsuite"},
            {"label": "Einstellungen", "action": "navigate", "payload": "/config/integrations"},
        ]
    else:
        personalities = {
            "copilot": "Helpful and proactive",
            "butler": "Stylish and discreet",
            "energy_manager": "Efficient and data-driven",
            "security_guard": "Vigilant and protective",
            "friendly": "Warm and talkative",
            "minimal": "Brief and direct",
        }
        greeting = f"Hello! I'm {agent}."
        message = (
            f"Welcome to PilotSuite! I'm {agent}, your personal "
            f"AI assistant for your smart home. I run completely locally "
            f"on your Home Assistant — your data stays with you.\n\n"
            f"I can help you with:\n"
            f"- Control devices and create automations\n"
            f"- Optimize energy usage and leverage electricity prices\n"
            f"- Evaluate weather warnings and react proactively\n"
            f"- Learn mood and habits\n"
            f"- And much more!"
        )
        quick_actions = [
            {"label": f"Test: Hello {agent}!", "action": "chat", "payload": f"Hello {agent}, what can you do?"},
            {"label": "Energy Status", "action": "chat", "payload": "What is my current energy status?"},
            {"label": "Open Dashboard", "action": "navigate", "payload": "/pilotsuite"},
            {"label": "Settings", "action": "navigate", "payload": "/config/integrations"},
        ]

    return WelcomeMessage(
        language=language,
        agent_name=agent,
        greeting=greeting,
        message=message,
        personality=personalities.get(character, "Helpful"),
        quick_actions=quick_actions,
    )


# ── API endpoints ────────────────────────────────────────────────────────


@onboarding_bp.route("/welcome", methods=["GET"])
@require_token
def get_welcome():
    """Get the Styx welcome message."""
    lang = request.args.get("lang", "de")
    welcome = get_welcome_message(language=lang)
    return jsonify({"ok": True, **asdict(welcome)})


@onboarding_bp.route("/state", methods=["GET"])
@require_token
def get_state():
    """Get current onboarding state."""
    session_id = request.args.get("session", "default")
    state = get_onboarding_state(session_id)
    return jsonify({"ok": True, **asdict(state)})


@onboarding_bp.route("/step/complete", methods=["POST"])
@require_token
def post_complete_step():
    """Mark an onboarding step as complete.

    JSON body: {"session": "default", "step_id": "welcome"}
    """
    body = request.get_json(silent=True) or {}
    session_id = body.get("session", "default")
    step_id = body.get("step_id", "")

    if not step_id:
        return jsonify({"ok": False, "error": "step_id required"}), 400

    state = complete_step(session_id, step_id)
    return jsonify({"ok": True, **asdict(state)})


@onboarding_bp.route("/step/skip", methods=["POST"])
@require_token
def post_skip_step():
    """Skip an onboarding step.

    JSON body: {"session": "default", "step_id": "regional_config"}
    """
    body = request.get_json(silent=True) or {}
    session_id = body.get("session", "default")
    step_id = body.get("step_id", "")

    if not step_id:
        return jsonify({"ok": False, "error": "step_id required"}), 400

    state = skip_step(session_id, step_id)
    return jsonify({"ok": True, **asdict(state)})


@onboarding_bp.route("/reset", methods=["POST"])
@require_token
def post_reset():
    """Reset onboarding state (start over)."""
    body = request.get_json(silent=True) or {}
    session_id = body.get("session", "default")

    if session_id in _onboarding_state:
        del _onboarding_state[session_id]

    state = get_onboarding_state(session_id)
    return jsonify({"ok": True, "reset": True, **asdict(state)})
