"""Zone Configuration API endpoint.

CRUD API for the Habitus zone configuration contract. The endpoint folds in:
- ZONE_TAXONOMY.md → canonical 10 zones
- RAUM_REGISTRY.md → explicit room/area mappings + aggregation rules
- AUTOMATION_MODULES.md → 7 module types with suggestion-first defaults

Contract highlights per zone:
- zone_id
- modules[]
- aggregation_rules
- fallback_semantics
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from copilot_core.api.error_models import ErrorResponse, error_response_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/zone-config", tags=["zone-config"])


MODULE_IDS: tuple[str, ...] = (
    "light",
    "motion",
    "music",
    "volume",
    "tv",
    "climate",
    "camera",
)

DEFAULT_SUGGESTION_MODE = "explainable_manual"
UNMATCHED_FALLBACK_ZONE_ID = "ungeordnet"

BASE_MODULE_PRIORITIES: dict[str, int] = {
    "motion": 100,
    "light": 95,
    "climate": 80,
    "music": 72,
    "volume": 68,
    "tv": 62,
    "camera": 58,
}

MODULE_PIPELINE_DEFAULTS: dict[str, dict[str, Any]] = {
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


ZONE_TAXONOMY: dict[str, dict[str, Any]] = {
    "wohnbereich": {
        "zone_type": "area",
        "name_de": "Wohnbereich",
        "name_en": "Living Area",
        "description": "Hauptaufenthaltsbereich zum Wohnen, Essen und Entspannen.",
        "keywords_de": ["wohn", "wohnzimmer", "esszimmer", "ess", "gast", "entspannung"],
        "keywords_en": ["living", "dining", "lounge", "loft"],
    },
    "badbereich": {
        "zone_type": "area",
        "name_de": "Badbereich",
        "name_en": "Bathroom Area",
        "description": "Sanitärzone für Bad, WC und Dusche.",
        "keywords_de": ["bad", "badezimmer", "toilette", "wc", "dusche"],
        "keywords_en": ["bath", "bathroom", "shower"],
    },
    "kochbereich": {
        "zone_type": "area",
        "name_de": "Kochbereich",
        "name_en": "Kitchen Area",
        "description": "Koch-, Vorrats- und Speiseflächen als gemeinsame Funktionszone.",
        "keywords_de": ["koch", "küche", "kueche", "speis", "vorrat"],
        "keywords_en": ["kitchen", "pantry"],
    },
    "buerobereich": {
        "zone_type": "room",
        "name_de": "Bürobereich",
        "name_en": "Office Area",
        "description": "Arbeits-, Studio- und Homeoffice-Zone.",
        "keywords_de": ["büro", "buero", "arbeit", "homeoffice"],
        "keywords_en": ["office", "studio", "workshop"],
    },
    "gangbereich": {
        "zone_type": "area",
        "name_de": "Gangbereich",
        "name_en": "Hallway Area",
        "description": "Verbindungs- und Eingangsflächen wie Flur, Diele oder Korridor.",
        "keywords_de": ["gang", "flur", "diele", "eingang", "korridor", "vorraum"],
        "keywords_en": ["hall", "corridor", "entry"],
    },
    "schlafbereich": {
        "zone_type": "room",
        "name_de": "Schlafbereich",
        "name_en": "Sleeping Area",
        "description": "Schlaf- und Ruhezonen.",
        "keywords_de": ["schlaf", "schlafzimmer"],
        "keywords_en": ["bedroom", "sleeping"],
    },
    "kellerbereich": {
        "zone_type": "room",
        "name_de": "Kellerbereich",
        "name_en": "Basement Area",
        "description": "Keller-, Speicher- und Lagerflächen.",
        "keywords_de": ["keller", "speicher", "lager"],
        "keywords_en": ["basement", "cellar", "storage"],
    },
    "zimmer_mira": {
        "zone_type": "room",
        "name_de": "Zimmer Mira",
        "name_en": "Mira Room",
        "description": "Individuelle Kinderzimmer-Zone für Mira.",
        "keywords_de": ["mira", "zimmer mira", "miras zimmer"],
        "keywords_en": ["mira room"],
    },
    "zimmer_paul": {
        "zone_type": "room",
        "name_de": "Zimmer Paul",
        "name_en": "Paul Room",
        "description": "Individuelle Kinderzimmer-Zone für Paul.",
        "keywords_de": ["paul", "zimmer paul", "pauls zimmer"],
        "keywords_en": ["paul room"],
    },
    "aussenbereich": {
        "zone_type": "outdoor",
        "name_de": "Außenbereich",
        "name_en": "Outdoor Area",
        "description": "Außenflächen wie Garten, Terrasse, Balkon, Garage oder Hof.",
        "keywords_de": ["aussen", "außen", "garten", "garage", "carport", "hof", "terrasse", "balkon"],
        "keywords_en": ["outdoor", "garden", "patio", "balcony", "garage"],
    },
}

ZONE_MODULE_DEFAULTS: dict[str, set[str]] = {
    "wohnbereich": {"light", "motion", "music", "volume", "tv", "climate"},
    "badbereich": {"light", "motion", "climate"},
    "kochbereich": {"light", "motion", "music", "volume", "climate"},
    "buerobereich": {"light", "motion", "music", "volume", "climate"},
    "gangbereich": {"light", "motion", "camera"},
    "schlafbereich": {"light", "motion", "music", "volume", "climate"},
    "aussenbereich": {"light", "motion", "camera"},
}

ZONE_TYPE_FALLBACK_DEFAULTS: dict[str, set[str]] = {
    "room": {"light", "motion", "music", "volume", "climate"},
    "area": {"light", "motion", "music", "volume", "climate"},
    "outdoor": {"light", "motion", "camera"},
    "floor": {"light", "motion", "climate"},
    "fallback": set(),
}

ZONE_MODULE_NOTES: dict[str, dict[str, str]] = {
    "wohnbereich": {
        "tv": "TV remains suggestion-first in shared living areas.",
        "camera": "Indoor cameras stay disabled by default in shared living areas.",
    },
    "badbereich": {
        "music": "Bathroom audio remains opt-in until explicitly enabled.",
        "camera": "Cameras stay disabled by default in private bathroom zones.",
    },
    "schlafbereich": {
        "tv": "Bedroom TV control remains opt-in and suggestion-first.",
        "camera": "Cameras stay disabled by default in sleeping zones.",
    },
    "zimmer_mira": {
        "tv": "Child-room TV control remains opt-in and suggestion-first.",
        "camera": "Child-room cameras stay disabled by default for privacy.",
    },
    "zimmer_paul": {
        "tv": "Child-room TV control remains opt-in and suggestion-first.",
        "camera": "Child-room cameras stay disabled by default for privacy.",
    },
    "aussenbereich": {
        "camera": "Outdoor cameras may suggest security actions, but direct execution remains disabled.",
        "music": "Outside audio stays disabled by default unless explicitly enabled.",
    },
}

ROOM_MAPPINGS: list[dict[str, Any]] = [
    {"area_id": "wohnzimmer", "zone_id": "wohnbereich", "zone_type": "area", "confidence": 1.0, "aggregated": False},
    {"area_id": "esszimmer", "zone_id": "wohnbereich", "zone_type": "area", "confidence": 1.0, "aggregated": True},
    {"area_id": "badezimmer", "zone_id": "badbereich", "zone_type": "area", "confidence": 1.0, "aggregated": False},
    {"area_id": "wc", "zone_id": "badbereich", "zone_type": "area", "confidence": 1.0, "aggregated": True},
    {"area_id": "kuche", "zone_id": "kochbereich", "zone_type": "area", "confidence": 1.0, "aggregated": False},
    {"area_id": "keller", "zone_id": "kellerbereich", "zone_type": "room", "confidence": 1.0, "aggregated": False},
    {"area_id": "zimmer_mira", "zone_id": "zimmer_mira", "zone_type": "room", "confidence": 1.0, "aggregated": False},
    {"area_id": "zimmer_paul", "zone_id": "zimmer_paul", "zone_type": "room", "confidence": 1.0, "aggregated": False},
    {"area_id": "flug", "zone_id": "gangbereich", "zone_type": "area", "confidence": 1.0, "aggregated": False},
    {"area_id": "schlafzimmer", "zone_id": "schlafbereich", "zone_type": "room", "confidence": 1.0, "aggregated": False},
]

AGGREGATION_RULES: list[dict[str, Any]] = [
    {"target_zone": "wohnbereich", "source_areas": ["wohnzimmer", "esszimmer", "gast"], "rule": "N:1"},
    {"target_zone": "badbereich", "source_areas": ["badezimmer", "wc", "dusche"], "rule": "N:1"},
    {"target_zone": "kochbereich", "source_areas": ["kuche", "speis", "vorrat"], "rule": "N:1"},
]


# In-memory registry seeded from the integrated taxonomy/room/module docs.
_zone_configs: dict[str, dict[str, Any]] = {}


class ZoneModuleConfigModel(BaseModel):
    module_id: str = Field(..., description="Stable module identifier")
    enabled: bool = Field(True, description="Whether the module is enabled for this zone")
    suggestion_mode: str = Field(DEFAULT_SUGGESTION_MODE, description="Suggestion mode for module actions")
    direct_execution_enabled: bool = Field(False, description="Allow direct execution without manual handoff")
    approval_required: bool = Field(True, description="Whether approval is required before execution")
    explanation_required: bool = Field(True, description="Whether an explanation is required for actions")
    autonomy_mode: str = Field("learning", description="Autonomy mode: learning|autonomous|off")
    module_category: str = Field("habitat", description="Logical module category")
    input_model: str = Field("NeuronInputV1", description="Input model name")
    pipeline_role: str = Field("adapter_to_brain", description="Pipeline role")
    priority: int = Field(50, description="Conflict priority")
    input_adapter: str = Field("homeassistant", description="Input adapter source")
    input_signals: List[str] = Field(default_factory=list, description="Signal domains consumed by the module")
    neuron_targets: List[str] = Field(default_factory=list, description="Neuron targets affected by the module")
    output_adapter: str = Field("homeassistant", description="Output adapter target")
    output_mode: str = Field("proposal_then_service_call", description="How module outputs are emitted")
    notes: str = Field("", description="Human guidance / rationale")


class RoomMappingModel(BaseModel):
    area_id: str = Field(..., description="Home Assistant area/room identifier")
    zone_id: str = Field(..., description="Resolved canonical zone identifier")
    zone_type: str = Field(..., description="Zone type for the mapping")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Mapping confidence")
    aggregated: bool = Field(False, description="Whether the mapping is part of an aggregation")


class AggregationRuleModel(BaseModel):
    target_zone: str = Field(..., description="Zone receiving the aggregated areas")
    source_areas: List[str] = Field(default_factory=list, description="Source areas participating in the aggregation")
    rule: str = Field("N:1", description="Aggregation cardinality rule")


class FallbackSemanticsModel(BaseModel):
    unmatched_fallback_zone_id: str = Field(
        UNMATCHED_FALLBACK_ZONE_ID,
        description="Zone used when no explicit mapping or taxonomy match exists",
    )
    mapping_resolution_order: List[str] = Field(
        default_factory=lambda: [
            "explicit_room_registry",
            "zone_taxonomy_keywords",
            "fallback_zone",
        ],
        description="Resolution order for zone assignment",
    )
    module_resolution: str = Field(
        "zone_specific_then_zone_type_defaults",
        description="How module defaults are resolved",
    )
    zone_type_default_modules: List[str] = Field(
        default_factory=list,
        description="Enabled modules inherited from the zone type fallback",
    )


class ZoneConfigModel(BaseModel):
    zone_id: str = Field(..., description="Canonical zone identifier")
    zone_type: str = Field(..., description="Zone type: room|area|outdoor|fallback")
    name_de: str = Field(..., description="German display name")
    name_en: str = Field(..., description="English display name")
    description: str = Field(..., description="Zone description")
    keywords_de: List[str] = Field(default_factory=list, description="German taxonomy keywords")
    keywords_en: List[str] = Field(default_factory=list, description="English taxonomy keywords")
    modules: List[ZoneModuleConfigModel] = Field(default_factory=list, description="Resolved automation module configs")
    room_mappings: List[RoomMappingModel] = Field(default_factory=list, description="Explicit room/area mappings")
    aggregation_rules: List[AggregationRuleModel] = Field(default_factory=list, description="Aggregation rules targeting this zone")
    fallback_semantics: FallbackSemanticsModel = Field(..., description="Fallback semantics for unmatched rooms and defaults")


class ZoneConfigListResponse(BaseModel):
    total_zones: int = Field(..., description="Number of canonical configured zones")
    supported_module_ids: List[str] = Field(default_factory=list, description="Supported automation module IDs")
    unmatched_fallback_zone_id: str = Field(..., description="Global unmatched fallback zone")
    zones: List[ZoneConfigModel] = Field(default_factory=list, description="All zone configs")


class ZoneConfigMutationRequest(BaseModel):
    zone_id: str = Field(..., description="Canonical zone identifier to mutate")
    zone_type: Optional[str] = Field(None, description="Optional zone type override")
    name_de: Optional[str] = Field(None, description="Optional German name override")
    name_en: Optional[str] = Field(None, description="Optional English name override")
    description: Optional[str] = Field(None, description="Optional zone description override")
    keywords_de: Optional[List[str]] = Field(None, description="Optional German keywords override")
    keywords_en: Optional[List[str]] = Field(None, description="Optional English keywords override")
    modules: Optional[List[ZoneModuleConfigModel]] = Field(None, description="Optional module override list")
    room_mappings: Optional[List[RoomMappingModel]] = Field(None, description="Optional explicit room mapping override")
    aggregation_rules: Optional[List[AggregationRuleModel]] = Field(None, description="Optional aggregation rule override")
    fallback_semantics: Optional[FallbackSemanticsModel] = Field(None, description="Optional fallback semantics override")


def _model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _zone_config_error_response(
    status_code: int,
    *,
    code: str,
    message: str,
    field: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response_payload(code=code, message=message, field=field, context=context),
    )


def _default_note(zone_id: str, module_id: str, enabled: bool) -> str:
    zone_note = ZONE_MODULE_NOTES.get(zone_id, {}).get(module_id)
    if zone_note:
        return zone_note
    if enabled:
        return "Suggestion-first with explanation; direct execution stays disabled by default."
    return "Disabled by default for this zone; explicitly enable if you want suggestions here."


def _default_modules_for(zone_id: str, zone_type: str) -> list[dict[str, Any]]:
    enabled_modules = set(
        ZONE_MODULE_DEFAULTS.get(zone_id, ZONE_TYPE_FALLBACK_DEFAULTS.get(zone_type, set()))
    )
    modules: list[dict[str, Any]] = []
    for module_id in MODULE_IDS:
        pipeline = MODULE_PIPELINE_DEFAULTS.get(module_id, {})
        enabled = module_id in enabled_modules
        modules.append(
            {
                "module_id": module_id,
                "enabled": enabled,
                "suggestion_mode": DEFAULT_SUGGESTION_MODE,
                "direct_execution_enabled": False,
                "approval_required": True,
                "explanation_required": True,
                "autonomy_mode": "learning",
                "module_category": "habitat",
                "input_model": "NeuronInputV1",
                "pipeline_role": "adapter_to_brain",
                "priority": BASE_MODULE_PRIORITIES.get(module_id, 50),
                "input_adapter": str(pipeline.get("input_adapter", "homeassistant")),
                "input_signals": list(pipeline.get("input_signals", [])),
                "neuron_targets": list(pipeline.get("neuron_targets", [])),
                "output_adapter": str(pipeline.get("output_adapter", "homeassistant")),
                "output_mode": str(pipeline.get("output_mode", "proposal_then_service_call")),
                "notes": _default_note(zone_id, module_id, enabled),
            }
        )
    return modules


def _default_room_mappings_for(zone_id: str) -> list[dict[str, Any]]:
    return [copy.deepcopy(mapping) for mapping in ROOM_MAPPINGS if mapping["zone_id"] == zone_id]


def _default_aggregation_rules_for(zone_id: str) -> list[dict[str, Any]]:
    return [copy.deepcopy(rule) for rule in AGGREGATION_RULES if rule["target_zone"] == zone_id]


def _default_fallback_semantics_for(zone_id: str, zone_type: str) -> dict[str, Any]:
    del zone_id  # semantics are currently zone-type driven + shared fallback
    return {
        "unmatched_fallback_zone_id": UNMATCHED_FALLBACK_ZONE_ID,
        "mapping_resolution_order": [
            "explicit_room_registry",
            "zone_taxonomy_keywords",
            "fallback_zone",
        ],
        "module_resolution": "zone_specific_then_zone_type_defaults",
        "zone_type_default_modules": sorted(ZONE_TYPE_FALLBACK_DEFAULTS.get(zone_type, set())),
    }


def _build_default_zone_config(zone_id: str) -> dict[str, Any]:
    taxonomy = ZONE_TAXONOMY[zone_id]
    zone_type = str(taxonomy["zone_type"])
    return {
        "zone_id": zone_id,
        "zone_type": zone_type,
        "name_de": str(taxonomy["name_de"]),
        "name_en": str(taxonomy["name_en"]),
        "description": str(taxonomy["description"]),
        "keywords_de": list(taxonomy.get("keywords_de", [])),
        "keywords_en": list(taxonomy.get("keywords_en", [])),
        "modules": _default_modules_for(zone_id, zone_type),
        "room_mappings": _default_room_mappings_for(zone_id),
        "aggregation_rules": _default_aggregation_rules_for(zone_id),
        "fallback_semantics": _default_fallback_semantics_for(zone_id, zone_type),
    }


def _default_registry() -> dict[str, dict[str, Any]]:
    return {zone_id: _build_default_zone_config(zone_id) for zone_id in ZONE_TAXONOMY}


def _ensure_registry() -> None:
    global _zone_configs
    if not _zone_configs:
        _zone_configs = _default_registry()


def _normalize_zone_id(zone_id: str) -> str:
    return str(zone_id or "").strip().lower()


def _validate_zone_id(zone_id: str) -> Optional[JSONResponse]:
    if zone_id in ZONE_TAXONOMY:
        return None
    return _zone_config_error_response(
        400,
        code="INVALID_ZONE_ID",
        message=f"Ungültige Zone-ID: {zone_id}.",
        field="zone_id",
        context={"allowed_values": list(ZONE_TAXONOMY.keys())},
    )


def _merge_modules(
    zone_id: str,
    zone_type: str,
    current_modules: list[dict[str, Any]],
    incoming_modules: Optional[list[ZoneModuleConfigModel]],
) -> list[dict[str, Any]]:
    if incoming_modules is None:
        return copy.deepcopy(current_modules)

    default_by_id = {
        module["module_id"]: module
        for module in _default_modules_for(zone_id, zone_type)
    }
    current_by_id = {
        module["module_id"]: copy.deepcopy(module)
        for module in current_modules
    }
    merged = {module_id: copy.deepcopy(default_by_id[module_id]) for module_id in MODULE_IDS}
    for module_id, payload in current_by_id.items():
        if module_id in merged:
            merged[module_id].update(payload)

    for incoming in incoming_modules:
        payload = _model_dump(incoming)
        module_id = str(payload.get("module_id") or "").strip().lower()
        if module_id not in MODULE_IDS:
            raise ValueError(module_id)
        merged[module_id].update(payload)
        merged[module_id]["module_id"] = module_id

    return [merged[module_id] for module_id in MODULE_IDS]


def _merge_zone_config(
    zone_id: str,
    request_model: ZoneConfigMutationRequest,
    *,
    replace: bool,
) -> dict[str, Any]:
    default_zone = _build_default_zone_config(zone_id)
    current_zone = copy.deepcopy(_zone_configs.get(zone_id, default_zone))
    result = copy.deepcopy(default_zone if replace else current_zone)
    payload = _model_dump(request_model)

    zone_type = str(payload.get("zone_type") or result["zone_type"]).strip().lower()
    if zone_type not in ZONE_TYPE_FALLBACK_DEFAULTS:
        raise RuntimeError("invalid_zone_type")
    result["zone_type"] = zone_type

    for field_name in ("name_de", "name_en", "description"):
        if payload.get(field_name) is not None:
            result[field_name] = str(payload[field_name])

    for field_name in ("keywords_de", "keywords_en"):
        if payload.get(field_name) is not None:
            result[field_name] = [str(item) for item in payload[field_name] if str(item).strip()]

    result["modules"] = _merge_modules(
        zone_id,
        zone_type,
        result.get("modules", []),
        request_model.modules,
    )

    if request_model.room_mappings is not None:
        room_mappings: list[dict[str, Any]] = []
        for mapping in request_model.room_mappings:
            data = _model_dump(mapping)
            if _normalize_zone_id(data.get("zone_id", "")) != zone_id:
                raise RuntimeError("room_mapping_zone_mismatch")
            room_mappings.append(data)
        result["room_mappings"] = room_mappings

    if request_model.aggregation_rules is not None:
        aggregation_rules: list[dict[str, Any]] = []
        for rule in request_model.aggregation_rules:
            data = _model_dump(rule)
            if _normalize_zone_id(data.get("target_zone", "")) != zone_id:
                raise RuntimeError("aggregation_rule_zone_mismatch")
            aggregation_rules.append(data)
        result["aggregation_rules"] = aggregation_rules

    if request_model.fallback_semantics is not None:
        fallback = _default_fallback_semantics_for(zone_id, zone_type)
        fallback.update(_model_dump(request_model.fallback_semantics))
        result["fallback_semantics"] = fallback
    elif replace:
        result["fallback_semantics"] = _default_fallback_semantics_for(zone_id, zone_type)

    # Keep fallback semantics aligned with the effective zone_type defaults.
    result["fallback_semantics"]["zone_type_default_modules"] = sorted(
        ZONE_TYPE_FALLBACK_DEFAULTS.get(zone_type, set())
    )

    return result


@router.get(
    "",
    response_model=ZoneConfigListResponse,
    responses={400: {"model": ErrorResponse}},
)
async def list_zone_configs() -> ZoneConfigListResponse:
    """Return all canonical zone configs derived from taxonomy, room registry and module defaults."""
    _ensure_registry()
    zones = [ZoneConfigModel(**copy.deepcopy(_zone_configs[zone_id])) for zone_id in ZONE_TAXONOMY]
    return ZoneConfigListResponse(
        total_zones=len(zones),
        supported_module_ids=list(MODULE_IDS),
        unmatched_fallback_zone_id=UNMATCHED_FALLBACK_ZONE_ID,
        zones=zones,
    )


@router.get(
    "/{zone_id}",
    response_model=ZoneConfigModel,
    responses={400: {"model": ErrorResponse}},
)
async def get_zone_config(zone_id: str):
    """Return the config for a single canonical zone."""
    _ensure_registry()
    normalized_zone_id = _normalize_zone_id(zone_id)
    error = _validate_zone_id(normalized_zone_id)
    if error is not None:
        return error
    return ZoneConfigModel(**copy.deepcopy(_zone_configs[normalized_zone_id]))


@router.post(
    "",
    response_model=ZoneConfigModel,
    responses={400: {"model": ErrorResponse}},
)
async def create_zone_config(request: ZoneConfigMutationRequest):
    """Upsert a canonical zone config by zone_id."""
    _ensure_registry()
    zone_id = _normalize_zone_id(request.zone_id)
    error = _validate_zone_id(zone_id)
    if error is not None:
        return error

    try:
        updated = _merge_zone_config(zone_id, request, replace=False)
    except ValueError as exc:
        return _zone_config_error_response(
            400,
            code="INVALID_MODULE_ID",
            message=f"Ungültige Modul-ID: {exc.args[0]}.",
            field="modules",
            context={"allowed_values": list(MODULE_IDS)},
        )
    except RuntimeError as exc:
        if str(exc) == "invalid_zone_type":
            return _zone_config_error_response(
                400,
                code="INVALID_ZONE_TYPE",
                message="Ungültiger Zone-Typ für Zone-Config.",
                field="zone_type",
                context={"allowed_values": list(ZONE_TYPE_FALLBACK_DEFAULTS.keys())},
            )
        if str(exc) == "room_mapping_zone_mismatch":
            return _zone_config_error_response(
                400,
                code="ROOM_MAPPING_ZONE_MISMATCH",
                message="Alle room_mappings müssen auf dieselbe zone_id zeigen.",
                field="room_mappings",
            )
        if str(exc) == "aggregation_rule_zone_mismatch":
            return _zone_config_error_response(
                400,
                code="AGGREGATION_RULE_ZONE_MISMATCH",
                message="Alle aggregation_rules müssen dieselbe target_zone verwenden.",
                field="aggregation_rules",
            )
        raise

    _zone_configs[zone_id] = updated
    logger.info("Updated zone-config via POST: %s", zone_id)
    return ZoneConfigModel(**copy.deepcopy(updated))


@router.put(
    "/{zone_id}",
    response_model=ZoneConfigModel,
    responses={400: {"model": ErrorResponse}},
)
async def replace_zone_config(zone_id: str, request: ZoneConfigMutationRequest):
    """Replace a canonical zone config. Omitted fields fall back to taxonomy defaults."""
    _ensure_registry()
    normalized_zone_id = _normalize_zone_id(zone_id)
    error = _validate_zone_id(normalized_zone_id)
    if error is not None:
        return error

    request_zone_id = _normalize_zone_id(request.zone_id)
    if request_zone_id != normalized_zone_id:
        return _zone_config_error_response(
            400,
            code="ZONE_ID_MISMATCH",
            message="Path zone_id und Body zone_id müssen identisch sein.",
            field="zone_id",
            context={"path_zone_id": normalized_zone_id, "body_zone_id": request_zone_id},
        )

    try:
        updated = _merge_zone_config(normalized_zone_id, request, replace=True)
    except ValueError as exc:
        return _zone_config_error_response(
            400,
            code="INVALID_MODULE_ID",
            message=f"Ungültige Modul-ID: {exc.args[0]}.",
            field="modules",
            context={"allowed_values": list(MODULE_IDS)},
        )
    except RuntimeError as exc:
        if str(exc) == "invalid_zone_type":
            return _zone_config_error_response(
                400,
                code="INVALID_ZONE_TYPE",
                message="Ungültiger Zone-Typ für Zone-Config.",
                field="zone_type",
                context={"allowed_values": list(ZONE_TYPE_FALLBACK_DEFAULTS.keys())},
            )
        if str(exc) == "room_mapping_zone_mismatch":
            return _zone_config_error_response(
                400,
                code="ROOM_MAPPING_ZONE_MISMATCH",
                message="Alle room_mappings müssen auf dieselbe zone_id zeigen.",
                field="room_mappings",
            )
        if str(exc) == "aggregation_rule_zone_mismatch":
            return _zone_config_error_response(
                400,
                code="AGGREGATION_RULE_ZONE_MISMATCH",
                message="Alle aggregation_rules müssen dieselbe target_zone verwenden.",
                field="aggregation_rules",
            )
        raise

    _zone_configs[normalized_zone_id] = updated
    logger.info("Replaced zone-config via PUT: %s", normalized_zone_id)
    return ZoneConfigModel(**copy.deepcopy(updated))


@router.delete(
    "/{zone_id}",
    responses={400: {"model": ErrorResponse}},
)
async def delete_zone_config(zone_id: str):
    """Reset a canonical zone back to the integrated defaults.

    Canonical taxonomy zones are not physically deleted; DELETE restores the
    default config derived from taxonomy + room registry + automation modules.
    """
    _ensure_registry()
    normalized_zone_id = _normalize_zone_id(zone_id)
    error = _validate_zone_id(normalized_zone_id)
    if error is not None:
        return error

    reset_zone = _build_default_zone_config(normalized_zone_id)
    _zone_configs[normalized_zone_id] = reset_zone
    logger.info("Reset zone-config via DELETE: %s", normalized_zone_id)
    return {
        "ok": True,
        "action": "reset_to_defaults",
        "zone": ZoneConfigModel(**copy.deepcopy(reset_zone)),
    }
