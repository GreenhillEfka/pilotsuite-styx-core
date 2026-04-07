"""
Habituszone-Definitionen für PilotSuite Styx Core

Definiert 10 standardisierte Habituszonen mit Keywords für ML-basiertes Matching.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional


class ZoneType(str, Enum):
    """Typen von Habituszonen."""
    LIVING = "living"
    BATH = "bath"
    KITCHEN = "kitchen"
    OFFICE = "office"
    HALLWAY = "hallway"
    BEDROOM = "bedroom"
    ROOM_MIRA = "room_mira"
    ROOM_PAUL = "room_paul"
    TERRACE = "terrace"
    OUTSIDE = "outside"


MODULE_OVERRIDE_IDS: tuple[str, ...] = (
    "light",
    "motion",
    "music",
    "volume",
    "tv",
    "climate",
    "camera",
)

DEFAULT_SUGGESTION_MODE = "explainable_manual"

_BASE_MODULE_PRIORITIES: dict[str, int] = {
    "motion": 100,
    "light": 95,
    "climate": 80,
    "music": 72,
    "volume": 68,
    "tv": 62,
    "camera": 58,
}

_MODULE_PIPELINE_DEFAULTS: dict[str, dict[str, Any]] = {
    "light": {
        "input_adapter": "homeassistant",
        "input_signals": ["light", "sensor", "binary_sensor"],
        "neuron_targets": ["ambient_need", "presence_intent"],
        "output_adapter": "homeassistant",
        "output_mode": "service_call_or_proposal",
    },
    "motion": {
        "input_adapter": "homeassistant",
        "input_signals": ["binary_sensor", "camera", "person", "device_tracker"],
        "neuron_targets": ["presence_intent", "stimulation_need"],
        "output_adapter": "homeassistant",
        "output_mode": "state_feedback",
    },
    "music": {
        "input_adapter": "homeassistant",
        "input_signals": ["media_player", "remote"],
        "neuron_targets": ["media_tolerance", "stimulation_need", "rest_need"],
        "output_adapter": "homeassistant",
        "output_mode": "proposal_then_service_call",
    },
    "volume": {
        "input_adapter": "homeassistant",
        "input_signals": ["media_player", "remote", "sensor"],
        "neuron_targets": ["media_tolerance", "rest_need"],
        "output_adapter": "homeassistant",
        "output_mode": "proposal_then_service_call",
    },
    "tv": {
        "input_adapter": "homeassistant",
        "input_signals": ["media_player", "remote", "binary_sensor"],
        "neuron_targets": ["media_tolerance", "presence_intent"],
        "output_adapter": "homeassistant",
        "output_mode": "proposal_then_service_call",
    },
    "climate": {
        "input_adapter": "homeassistant",
        "input_signals": ["climate", "sensor", "binary_sensor"],
        "neuron_targets": ["rest_need", "ambient_need"],
        "output_adapter": "homeassistant",
        "output_mode": "proposal_then_service_call",
    },
    "camera": {
        "input_adapter": "homeassistant",
        "input_signals": ["camera", "binary_sensor"],
        "neuron_targets": ["presence_intent"],
        "output_adapter": "homeassistant",
        "output_mode": "observe_and_propose",
    },
}

_ZONE_ENABLED_MODULES: dict[ZoneType, set[str]] = {
    ZoneType.LIVING: {"light", "motion", "music", "volume", "tv", "climate"},
    ZoneType.BATH: {"light", "motion", "climate"},
    ZoneType.KITCHEN: {"light", "motion", "music", "volume", "climate"},
    ZoneType.OFFICE: {"light", "motion", "music", "volume", "climate"},
    ZoneType.HALLWAY: {"light", "motion", "camera"},
    ZoneType.BEDROOM: {"light", "motion", "music", "volume", "climate"},
    ZoneType.ROOM_MIRA: {"light", "motion", "music", "volume", "climate"},
    ZoneType.ROOM_PAUL: {"light", "motion", "music", "volume", "climate"},
    ZoneType.TERRACE: {"light", "motion", "music", "volume", "camera"},
    ZoneType.OUTSIDE: {"light", "motion", "camera"},
}

_ZONE_MODULE_NOTES: dict[ZoneType, dict[str, str]] = {
    ZoneType.LIVING: {
        "tv": "TV stays suggestion-first in shared living areas to avoid surprising playback changes.",
        "camera": "Indoor cameras stay disabled by default in shared living areas.",
    },
    ZoneType.BATH: {
        "music": "Bathroom audio remains opt-in until explicitly enabled.",
        "camera": "Cameras remain disabled by default in private sanitation zones.",
    },
    ZoneType.BEDROOM: {
        "tv": "Bedroom TV changes require explicit opt-in even when a TV exists.",
        "camera": "Cameras remain disabled by default in private sleeping zones.",
    },
    ZoneType.ROOM_MIRA: {
        "tv": "Child-room TV control stays suggestion-only and opt-in by default.",
        "camera": "Child-room cameras stay disabled by default for privacy.",
    },
    ZoneType.ROOM_PAUL: {
        "tv": "Child-room TV control stays suggestion-only and opt-in by default.",
        "camera": "Child-room cameras stay disabled by default for privacy.",
    },
    ZoneType.TERRACE: {
        "camera": "Outdoor-adjacent terrace cameras remain suggestion-first even when enabled.",
    },
    ZoneType.OUTSIDE: {
        "camera": "Outdoor cameras may suggest security actions, but direct execution stays disabled.",
        "music": "Outside audio stays disabled by default unless the zone is explicitly entertainment-focused.",
    },
}


@dataclass(frozen=True)
class HabitusZoneModuleOverride:
    """Policy defaults for a zone/module pair."""

    module_id: str
    enabled: bool = True
    suggestion_mode: str = DEFAULT_SUGGESTION_MODE
    direct_execution_enabled: bool = False
    approval_required: bool = True
    explanation_required: bool = True
    autonomy_mode: str = "learning"
    module_category: str = "habitat"
    input_model: str = "NeuronInputV1"
    pipeline_role: str = "adapter_to_brain"
    priority: int = 50
    input_adapter: str = "homeassistant"
    input_signals: List[str] = field(default_factory=list)
    neuron_targets: List[str] = field(default_factory=list)
    output_adapter: str = "homeassistant"
    output_mode: str = "proposal_then_service_call"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "module_id": self.module_id,
            "enabled": self.enabled,
            "suggestion_mode": self.suggestion_mode,
            "direct_execution_enabled": self.direct_execution_enabled,
            "approval_required": self.approval_required,
            "explanation_required": self.explanation_required,
            "autonomy_mode": self.autonomy_mode,
            "module_category": self.module_category,
            "input_model": self.input_model,
            "pipeline_role": self.pipeline_role,
            "priority": self.priority,
            "input_adapter": self.input_adapter,
            "input_signals": list(self.input_signals),
            "neuron_targets": list(self.neuron_targets),
            "output_adapter": self.output_adapter,
            "output_mode": self.output_mode,
            "notes": self.notes,
        }


@dataclass
class HabitusZone:
    """Eine Habituszone mit Keywords und Metadaten."""

    zone_type: ZoneType
    name_de: str  # Deutscher Name
    name_en: str  # Englischer Name
    keywords_de: List[str] = field(default_factory=list)  # Deutsche Keywords
    keywords_en: List[str] = field(default_factory=list)  # Englische Keywords
    priority: int = 0  # Höhere Priorität bei Konflikten
    description: str = ""
    module_overrides: Dict[str, HabitusZoneModuleOverride] = field(default_factory=dict)

    def get_all_keywords(self) -> List[str]:
        """Alle Keywords (DE + EN) zurückgeben."""
        return self.keywords_de + self.keywords_en

    def get_module_overrides(self) -> Dict[str, dict[str, Any]]:
        """Return serialized module overrides for API responses."""
        return {module_id: override.to_dict() for module_id, override in self.module_overrides.items()}


def _build_default_module_override(zone_type: ZoneType, module_id: str) -> HabitusZoneModuleOverride:
    enabled = module_id in _ZONE_ENABLED_MODULES.get(zone_type, set())
    notes = _ZONE_MODULE_NOTES.get(zone_type, {}).get(module_id, "")
    if not notes:
        if enabled:
            notes = "Suggestion-first with explanation; direct execution stays disabled by default."
        else:
            notes = "Disabled by default for this zone type; can be explicitly enabled later."

    pipeline_defaults = _MODULE_PIPELINE_DEFAULTS.get(module_id, {})

    return HabitusZoneModuleOverride(
        module_id=module_id,
        enabled=enabled,
        suggestion_mode=DEFAULT_SUGGESTION_MODE,
        direct_execution_enabled=False,
        approval_required=True,
        explanation_required=True,
        autonomy_mode="learning",
        module_category="habitat",
        input_model="NeuronInputV1",
        pipeline_role="adapter_to_brain",
        priority=_BASE_MODULE_PRIORITIES.get(module_id, 50),
        input_adapter=str(pipeline_defaults.get("input_adapter", "homeassistant")),
        input_signals=list(pipeline_defaults.get("input_signals", [])),
        neuron_targets=list(pipeline_defaults.get("neuron_targets", [])),
        output_adapter=str(pipeline_defaults.get("output_adapter", "homeassistant")),
        output_mode=str(pipeline_defaults.get("output_mode", "proposal_then_service_call")),
        notes=notes,
    )


def get_default_module_override_models(zone_type: ZoneType) -> Dict[str, HabitusZoneModuleOverride]:
    """Return typed default module overrides for a zone type."""
    return {
        module_id: _build_default_module_override(zone_type, module_id)
        for module_id in MODULE_OVERRIDE_IDS
    }


def get_default_module_overrides(zone_type: ZoneType) -> Dict[str, dict[str, Any]]:
    """Return serialized default module overrides for a zone type."""
    return {
        module_id: override.to_dict()
        for module_id, override in get_default_module_override_models(zone_type).items()
    }


def resolve_module_overrides(
    zone_type: ZoneType,
    overrides: Optional[Mapping[str, Any]],
) -> Dict[str, dict[str, Any]]:
    """Merge partial override input onto zone defaults.

    Unknown module ids are ignored. Each known module always appears in the result.
    """
    resolved = get_default_module_overrides(zone_type)
    if not isinstance(overrides, Mapping):
        return resolved

    for module_id, payload in overrides.items():
        if module_id not in resolved or not isinstance(payload, Mapping):
            continue

        current = dict(resolved[module_id])
        if "enabled" in payload:
            current["enabled"] = bool(payload.get("enabled"))
        if "suggestion_mode" in payload and payload.get("suggestion_mode"):
            current["suggestion_mode"] = str(payload.get("suggestion_mode"))
        if "direct_execution_enabled" in payload:
            current["direct_execution_enabled"] = bool(payload.get("direct_execution_enabled"))
        if "approval_required" in payload:
            current["approval_required"] = bool(payload.get("approval_required"))
        if "explanation_required" in payload:
            current["explanation_required"] = bool(payload.get("explanation_required"))
        if "autonomy_mode" in payload and payload.get("autonomy_mode"):
            current["autonomy_mode"] = str(payload.get("autonomy_mode"))
        if "module_category" in payload and payload.get("module_category"):
            current["module_category"] = str(payload.get("module_category"))
        if "input_model" in payload and payload.get("input_model"):
            current["input_model"] = str(payload.get("input_model"))
        if "pipeline_role" in payload and payload.get("pipeline_role"):
            current["pipeline_role"] = str(payload.get("pipeline_role"))
        if "priority" in payload:
            try:
                current["priority"] = int(payload.get("priority"))
            except (TypeError, ValueError):
                pass
        if "input_adapter" in payload and payload.get("input_adapter"):
            current["input_adapter"] = str(payload.get("input_adapter"))
        if "input_signals" in payload and isinstance(payload.get("input_signals"), (list, tuple)):
            current["input_signals"] = [str(v) for v in payload.get("input_signals") if v]
        if "neuron_targets" in payload and isinstance(payload.get("neuron_targets"), (list, tuple)):
            current["neuron_targets"] = [str(v) for v in payload.get("neuron_targets") if v]
        if "output_adapter" in payload and payload.get("output_adapter"):
            current["output_adapter"] = str(payload.get("output_adapter"))
        if "output_mode" in payload and payload.get("output_mode"):
            current["output_mode"] = str(payload.get("output_mode"))
        if "notes" in payload:
            current["notes"] = str(payload.get("notes") or "")

        resolved[module_id] = current

    return resolved


VALID_AUTONOMY_MODES: tuple[str, ...] = ("autonomous", "learning", "off")


def normalize_autonomy_mode(value: Any) -> str:
    """Return a supported autonomy mode with a safe default."""
    mode = str(value or "learning").strip().lower()
    return mode if mode in VALID_AUTONOMY_MODES else "learning"


def infer_module_id_for_action(action: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Infer the module policy bucket for a proposal/action payload."""
    if not isinstance(action, Mapping):
        return None

    domain = str(action.get("domain") or "").strip().lower()
    service = str(action.get("suggested_service") or action.get("service") or "").strip().lower()
    entity_id = str(action.get("entity_id") or "").strip().lower()
    haystack = " ".join(
        str(value or "")
        for value in (
            action.get("label"),
            action.get("title"),
            action.get("summary"),
            action.get("state"),
            entity_id,
            service,
        )
    ).lower()

    if domain == "light" or entity_id.startswith("light."):
        return "light"
    if domain == "climate" or entity_id.startswith("climate."):
        return "climate"
    if domain == "camera" or entity_id.startswith("camera."):
        return "camera"
    if domain in {"media_player", "remote"} or entity_id.startswith("media_player.") or entity_id.startswith("remote."):
        if "volume" in service or any(token in haystack for token in ("volume", "lautst", "louder", "quieter")):
            return "volume"
        if any(token in haystack for token in (" tv", "tv.", "television", "chromecast", "apple tv", "fire tv", "roku", "webos", "samsung", "lg")):
            return "tv"
        return "music"
    return None


def resolve_module_override_for_action(
    zone_type: Optional[ZoneType],
    module_id: Optional[str],
    overrides: Optional[Mapping[str, Any]],
) -> Optional[dict[str, Any]]:
    """Resolve the policy override for a proposal/action module."""
    if not module_id:
        return None

    if isinstance(overrides, Mapping):
        payload = overrides.get(module_id)
        if isinstance(payload, Mapping):
            return dict(payload)

    if zone_type is not None:
        return get_default_module_overrides(zone_type).get(module_id)

    return None


def evaluate_action_policy(
    module_id: Optional[str],
    module_override: Optional[Mapping[str, Any]],
    *,
    explicit_styx_instruction: bool = False,
) -> dict[str, Any]:
    """Evaluate whether an accepted proposal may become an executable action."""
    override = dict(module_override) if isinstance(module_override, Mapping) else None
    autonomy_mode = normalize_autonomy_mode(override.get("autonomy_mode") if override else "learning")
    enabled = bool(override.get("enabled", True)) if override is not None else False
    direct_execution_enabled = bool(override.get("direct_execution_enabled", False)) if override is not None else False
    approval_required = bool(override.get("approval_required", True)) if override is not None else True
    explanation_required = bool(override.get("explanation_required", True)) if override is not None else True
    suggestion_mode = str(override.get("suggestion_mode") or DEFAULT_SUGGESTION_MODE) if override is not None else DEFAULT_SUGGESTION_MODE

    blocked_reasons: List[str] = []
    if not module_id:
        blocked_reasons.append("module_unmapped")
    if override is None:
        blocked_reasons.append("zone_policy_unresolved")
    if override is not None and not enabled:
        blocked_reasons.append("module_disabled")
    if autonomy_mode == "off":
        blocked_reasons.append("autonomy_off")

    if blocked_reasons:
        return {
            "module_id": module_id,
            "autonomy_mode": autonomy_mode,
            "suggestion_mode": suggestion_mode,
            "enabled": enabled,
            "direct_execution_enabled": direct_execution_enabled,
            "approval_required": approval_required,
            "explanation_required": explanation_required,
            "explicit_styx_instruction": bool(explicit_styx_instruction),
            "needs_explicit_styx_instruction": False,
            "eligible_for_execution": False,
            "execution_state": "blocked",
            "decision_source": "policy_block",
            "blocked_reasons": blocked_reasons,
        }

    if explicit_styx_instruction:
        return {
            "module_id": module_id,
            "autonomy_mode": autonomy_mode,
            "suggestion_mode": suggestion_mode,
            "enabled": enabled,
            "direct_execution_enabled": direct_execution_enabled,
            "approval_required": approval_required,
            "explanation_required": explanation_required,
            "explicit_styx_instruction": True,
            "needs_explicit_styx_instruction": False,
            "eligible_for_execution": True,
            "execution_state": "ready_for_execution",
            "decision_source": "styx_instruction",
            "blocked_reasons": [],
        }

    if autonomy_mode == "autonomous" and direct_execution_enabled and not approval_required:
        return {
            "module_id": module_id,
            "autonomy_mode": autonomy_mode,
            "suggestion_mode": suggestion_mode,
            "enabled": enabled,
            "direct_execution_enabled": direct_execution_enabled,
            "approval_required": approval_required,
            "explanation_required": explanation_required,
            "explicit_styx_instruction": False,
            "needs_explicit_styx_instruction": False,
            "eligible_for_execution": True,
            "execution_state": "ready_for_execution",
            "decision_source": "policy_autonomous",
            "blocked_reasons": [],
        }

    waiting_reasons: List[str] = []
    if autonomy_mode == "learning":
        waiting_reasons.append("learning_mode_requires_styx_instruction")
    if not direct_execution_enabled:
        waiting_reasons.append("direct_execution_disabled_by_default")
    if approval_required:
        waiting_reasons.append("approval_required")

    return {
        "module_id": module_id,
        "autonomy_mode": autonomy_mode,
        "suggestion_mode": suggestion_mode,
        "enabled": enabled,
        "direct_execution_enabled": direct_execution_enabled,
        "approval_required": approval_required,
        "explanation_required": explanation_required,
        "explicit_styx_instruction": False,
        "needs_explicit_styx_instruction": True,
        "eligible_for_execution": False,
        "execution_state": "awaiting_styx_instruction",
        "decision_source": "accepted_pending_instruction",
        "blocked_reasons": waiting_reasons,
    }


# Standard-Habituszonen
HABITUS_ZONES: Dict[ZoneType, HabitusZone] = {
    ZoneType.LIVING: HabitusZone(
        zone_type=ZoneType.LIVING,
        name_de="Wohnbereich",
        name_en="Living Area",
        keywords_de=["wohn", "wohnzimmer", "wohnzimmer", "aufenthalt", "gast", "gästezimmer", "esszimmer", "essbereich"],
        keywords_en=["living", "lounge", "sitting", "guest", "dining", "family room"],
        priority=10,
        description="Hauptaufenthaltsbereich zum Wohnen und Entspannen",
        module_overrides=get_default_module_override_models(ZoneType.LIVING),
    ),
    
    ZoneType.BATH: HabitusZone(
        zone_type=ZoneType.BATH,
        name_de="Badbereich",
        name_en="Bathroom Area",
        keywords_de=["bad", "badbereich", "badezimmer", "wc", "toilette", "toilettenbereich", "gäste-wc", "gästebad", "dusche", "waschraum"],
        keywords_en=["bath", "bathroom", "toilet", "wc", "shower", "powder room"],
        priority=10,
        description="Sanitärbereich mit Bad/WC",
        module_overrides=get_default_module_override_models(ZoneType.BATH),
    ),
    
    ZoneType.KITCHEN: HabitusZone(
        zone_type=ZoneType.KITCHEN,
        name_de="Kochbereich",
        name_en="Kitchen Area",
        keywords_de=["koch", "küche", "kochen", "kochbereich", "speis", "vorrat", "hauswirtschaft", "esszimmer", "essbereich"],
        keywords_en=["kitchen", "cooking", "pantry", "utility", "laundry", "dining room", "dining area"],
        priority=11,
        description="Koch-, Ess- und Wirtschaftsbereich",
        module_overrides=get_default_module_override_models(ZoneType.KITCHEN),
    ),
    
    ZoneType.OFFICE: HabitusZone(
        zone_type=ZoneType.OFFICE,
        name_de="Bürobereich",
        name_en="Office Area",
        keywords_de=["büro", "arbeit", "homeoffice", "arbeitszimmer", "studie"],
        keywords_en=["office", "work", "study", "home office", "workspace"],
        priority=8,
        description="Arbeits- und Heimbürobereich",
        module_overrides=get_default_module_override_models(ZoneType.OFFICE),
    ),
    
    ZoneType.HALLWAY: HabitusZone(
        zone_type=ZoneType.HALLWAY,
        name_de="Gangbereich",
        name_en="Hallway Area",
        keywords_de=["gang", "gangbereich", "flur", "flurbereich", "diele", "treppenhaus", "eingang", "eingangsbereich", "windfang"],
        keywords_en=["hallway", "hall", "corridor", "entry", "entrance", "foyer"],
        priority=5,
        description="Verbindungsbereich und Durchgang",
        module_overrides=get_default_module_override_models(ZoneType.HALLWAY),
    ),
    
    ZoneType.BEDROOM: HabitusZone(
        zone_type=ZoneType.BEDROOM,
        name_de="Schlafbereich",
        name_en="Bedroom Area",
        keywords_de=["schlaf", "schlafzimmer", "schlafraum", "master", "eltern", "schlafbereich", "elternschlafzimmer"],
        keywords_en=["bedroom", "sleep", "master bedroom", "parents"],
        priority=12,
        description="Hauptschlafbereich",
        module_overrides=get_default_module_override_models(ZoneType.BEDROOM),
    ),
    
    ZoneType.ROOM_MIRA: HabitusZone(
        zone_type=ZoneType.ROOM_MIRA,
        name_de="Zimmer Mira",
        name_en="Mira's Room",
        keywords_de=["mira", "kinderzimmer mira", "zimmer mira", "miras zimmer"],
        keywords_en=["mira", "mira room", "mira bedroom", "miras room"],
        priority=20,  # Hohe Priorität für spezifische Namen
        description="Persönliches Zimmer von Mira",
        module_overrides=get_default_module_override_models(ZoneType.ROOM_MIRA),
    ),
    
    ZoneType.ROOM_PAUL: HabitusZone(
        zone_type=ZoneType.ROOM_PAUL,
        name_de="Zimmer Paul",
        name_en="Paul's Room",
        keywords_de=["paul", "kinderzimmer paul", "zimmer paul", "pauls zimmer"],
        keywords_en=["paul", "paul room", "paul bedroom", "pauls room"],
        priority=20,  # Hohe Priorität für spezifische Namen
        description="Persönliches Zimmer von Paul",
        module_overrides=get_default_module_override_models(ZoneType.ROOM_PAUL),
    ),
    
    ZoneType.TERRACE: HabitusZone(
        zone_type=ZoneType.TERRACE,
        name_de="Terrassenbereich",
        name_en="Terrace Area",
        keywords_de=["terrass", "balkon", "loggia", "dachterrass"],
        keywords_en=["terrace", "balcony", "patio", "deck"],
        priority=8,
        description="Überdachte Aussenbereiche",
        module_overrides=get_default_module_override_models(ZoneType.TERRACE),
    ),
    
    ZoneType.OUTSIDE: HabitusZone(
        zone_type=ZoneType.OUTSIDE,
        name_de="Aussenbereich",
        name_en="Outside Area",
        keywords_de=["aussen", "außen", "garten", "hof", "vorgarten", "hintergarten", "garage", "carport", "abstell", "terrasse", "terrassenbereich", "balkon", "loggia"],
        keywords_en=["outside", "garden", "yard", "garage", "shed", "outdoor", "terrace", "balcony", "patio", "deck"],
        priority=9,
        description="Aussenbereiche und smart aggregierte Outdoor-Zonen",
        module_overrides=get_default_module_override_models(ZoneType.OUTSIDE),
    ),
}


def get_all_zones() -> List[HabitusZone]:
    """Alle Habituszonen als Liste zurückgeben."""
    return list(HABITUS_ZONES.values())


def get_zone_by_type(zone_type: ZoneType) -> Optional[HabitusZone]:
    """Eine Zone nach Typ zurückgeben."""
    return HABITUS_ZONES.get(zone_type)


def get_zone_keywords() -> Dict[str, ZoneType]:
    """
    Mapping von Keywords zu ZoneTypes für schnelles Lookup.
    Alle Keywords werden lowercase gespeichert.
    """
    keyword_map = {}
    for zone in HABITUS_ZONES.values():
        for keyword in zone.get_all_keywords():
            keyword_map[keyword.lower()] = zone.zone_type
    return keyword_map


# Lazy imports to avoid circular dependencies
def get_automation_neurons(zone_id: str) -> List[str]:
    """Gibt Neuron-IDs zurück, die zu Zonen-Automations gehören.
    
    Args:
        zone_id: Zone identifier (z.B. "living", "bath", etc.)
    
    Returns:
        Liste von Neuron-IDs
    """
    from copilot_core.neurons.presence import get_zone_presence_manager
    return get_zone_presence_manager().get_automation_neurons(zone_id)


def get_zone_synapses(zone_id: str) -> Dict[str, Any]:
    """Gibt die vollständige Synapsen-Map für eine Zone zurück.
    
    Args:
        zone_id: Zone identifier
    
    Returns:
        Dict mit:
            - zone_id
            - neurons: Liste der Neuron-IDs
            - presence: Aktueller Präsenz-Status
            - entity_map: HA entity_id -> neuron_id Mapping
    """
    from copilot_core.neurons.presence import get_zone_presence_manager
    return get_zone_presence_manager().get_zone_synapses(zone_id)
