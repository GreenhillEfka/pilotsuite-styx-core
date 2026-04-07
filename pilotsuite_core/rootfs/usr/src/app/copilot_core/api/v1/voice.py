"""Voice API Endpoints for Home Assistant Voice Assistant Integration.

Provides REST API for voice intent handling, context building, and proactive hints.

Endpoints:
- POST /api/v1/voice/intent - Process voice intent
- POST /api/v1/voice/control/parse - Parse voice control into canonical proposal surface
- POST /api/v1/voice/control/continue - Continue an existing voice dialog session explicitly
- POST /api/v1/voice/control/confirm - Materialize voice proposal into policy-gated action handoff
- GET  /api/v1/voice/context - Get current voice context
- GET  /api/v1/voice/hints - Get proactive voice hints
- POST /api/v1/voice/speak - Generate TTS response
- GET  /api/v1/voice/status - Voice system status

Features:
- HA Voice Assistant Intent-Handling
- Kontextbewusste Antworten (Stimmung, Tageszeit, Raum)
- Proaktive Hinweise bei wichtigen Erkenntnissen
- DE/EN Sprachunterstützung
- Integration mit Mood Engine und Habitus
"""
import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Blueprint, current_app, jsonify, request

from copilot_core.action_closure import get_action_closure_store
from copilot_core.homeassistant.habitat_adapter import wrap_accepted_proposal_action
from copilot_core.homeassistant.habitus_zones import (
    ZoneType,
    evaluate_action_policy,
    infer_module_id_for_action,
    resolve_module_override_for_action,
)
from copilot_core.voice.control_engine import (
    Language as ControlLanguage,
    VoiceCommand as ControlVoiceCommand,
    VoiceIntentType,
    create_voice_control_engine,
    looks_like_follow_up_resume_request,
)
from copilot_core.voice.voice_handler import VoiceIntentHandler, VoiceIntent, IntentType, VoiceResponse
from copilot_core.voice.context_builder import VoiceContextBuilder, VoiceContext
from copilot_core.voice.proactive import ProactiveVoiceHints, HintConfig, HintPriority

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("voice", __name__, url_prefix="/api/v1/voice")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    """Require authentication for all voice endpoints."""
    if not _validate_token(request):
        return jsonify({
            "error": "unauthorized",
            "message": "Valid X-Auth-Token or Bearer token required"
        }), 401


def _get_intent_handler() -> VoiceIntentHandler:
    """Get or create voice intent handler instance."""
    if not hasattr(current_app, '_voice_intent_handler'):
        # Initialize mood engine if available
        mood_engine = None
        try:
            from copilot_core.mood.engine import MoodEngine, MoodConfig, ZoneConfig
            
            # Create default mood config
            zone_config = ZoneConfig(
                name="wohnzimmer",
                motion_entities=["binary_sensor.wohnzimmer_motion"],
                light_entities=["light.wohnzimmer"],
                media_entities=["media_player.wohnzimmer"],
                illuminance_entity="sensor.wohnzimmer_illuminance",
            )
            
            mood_config = MoodConfig(zones={"wohnzimmer": zone_config})
            mood_engine = MoodEngine(mood_config)
            
        except Exception as e:
            _LOGGER.warning("Failed to initialize mood engine for voice: %s", e)
        
        # Initialize habitus service if available
        habitus_service = None
        try:
            from copilot_core.habitus.service import HabitusService
            from copilot_core.brain_graph.service import BrainGraphService
            from copilot_core.candidates.store import CandidateStore
            
            # Try to get existing instances
            if hasattr(current_app, '_habitus_service'):
                habitus_service = current_app._habitus_service
            
        except Exception as e:
            _LOGGER.warning("Failed to initialize habitus service for voice: %s", e)
        
        current_app._voice_intent_handler = VoiceIntentHandler(
            mood_engine=mood_engine,
            habitus_service=habitus_service,
            default_language="de",
        )
    
    return current_app._voice_intent_handler


def _get_context_builder() -> VoiceContextBuilder:
    """Get or create voice context builder instance."""
    if not hasattr(current_app, '_voice_context_builder'):
        current_app._voice_context_builder = VoiceContextBuilder()
    return current_app._voice_context_builder


def _get_proactive_hints() -> ProactiveVoiceHints:
    """Get or create proactive voice hints instance."""
    if not hasattr(current_app, '_voice_proactive_hints'):
        # Get mood engine and habitus service
        intent_handler = _get_intent_handler()
        
        config = HintConfig(
            enabled_types=[
                hint_type for hint_type in __import__('copilot_core.voice.proactive', fromlist=['HintType']).HintType
            ],
            min_priority=HintPriority.LOW,
            hint_cooldown_seconds=300,
            max_hints_per_hour=6,
        )
        
        current_app._voice_proactive_hints = ProactiveVoiceHints(
            mood_engine=intent_handler.mood_engine,
            habitus_service=intent_handler.habitus_service,
            config=config,
        )
    
    return current_app._voice_proactive_hints


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_zone_type(value: Any) -> Optional[ZoneType]:
    if value in (None, ""):
        return None
    try:
        return ZoneType(str(value))
    except ValueError as exc:
        raise ValueError(f"Invalid zone_type: {value}") from exc


def _normalize_voice_language(value: Any) -> Optional[ControlLanguage]:
    if value in (None, ""):
        return None
    normalized = str(value).strip().lower()
    if normalized == ControlLanguage.DE.value:
        return ControlLanguage.DE
    if normalized == ControlLanguage.EN.value:
        return ControlLanguage.EN
    raise ValueError(f"Unsupported voice language: {value}")


def _get_voice_control_engine():
    engine = getattr(current_app, "_voice_control_engine", None)
    if engine is None:
        engine = create_voice_control_engine()
        current_app._voice_control_engine = engine
    return engine


def _get_voice_control_proposals() -> dict[str, dict[str, Any]]:
    proposals = getattr(current_app, "_voice_control_proposals", None)
    if proposals is None:
        proposals = {}
        current_app._voice_control_proposals = proposals
    return proposals


def _normalize_zone_slug(zone_id: Any) -> str:
    zone = str(zone_id or "").strip().lower()
    if zone.startswith("zone:"):
        zone = zone.split(":", 1)[1]
    elif zone.startswith("zone_"):
        zone = zone[len("zone_"):]
    zone = re.sub(r"[^a-z0-9]+", "_", zone)
    return zone.strip("_")


def _default_module_id_for_voice_intent(intent_type: VoiceIntentType) -> Optional[str]:
    if intent_type in {
        VoiceIntentType.TURN_ON,
        VoiceIntentType.TURN_OFF,
        VoiceIntentType.DIM,
        VoiceIntentType.BRIGHTEN,
        VoiceIntentType.SET_COLOR,
    }:
        return "light"
    if intent_type in {VoiceIntentType.CLIMATE_SET, VoiceIntentType.SET_TEMPERATURE}:
        return "climate"
    if intent_type in {
        VoiceIntentType.COVER_OPEN,
        VoiceIntentType.COVER_CLOSE,
        VoiceIntentType.COVER_POSITION,
    }:
        return "cover"
    return None


def _default_entity_id(module_id: Optional[str], zone_id: Optional[str]) -> Optional[str]:
    if not module_id or not zone_id:
        return None

    slug = _normalize_zone_slug(zone_id)
    if not slug:
        return None

    domain_map = {
        "light": "light",
        "climate": "climate",
        "music": "media_player",
        "volume": "media_player",
        "tv": "media_player",
        "camera": "camera",
        "cover": "cover",
    }
    domain = domain_map.get(module_id)
    if not domain:
        return None
    return f"{domain}.{slug}"


def _build_service_call_preview(action: dict[str, Any]) -> dict[str, Any]:
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    entity_id = str(action.get("entity_id") or target.get("entity_id") or "").strip()
    if entity_id and "entity_id" not in target:
        target = {**target, "entity_id": entity_id}

    preview = {
        "domain": str(action.get("domain") or "").strip().lower(),
        "service": str(action.get("suggested_service") or action.get("service") or "").strip().lower(),
        "target": target,
        "expected_state": action.get("state") if action.get("state") is not None else action.get("expected_state"),
    }
    payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
    if payload:
        preview["payload"] = dict(payload)
    return preview


def _voice_action_payload(intent_type: VoiceIntentType, command: ControlVoiceCommand) -> tuple[str, str, Any, dict[str, Any]]:
    if intent_type == VoiceIntentType.TURN_ON:
        return "light", "turn_on", "on", {}
    if intent_type == VoiceIntentType.TURN_OFF:
        return "light", "turn_off", "off", {}
    if intent_type == VoiceIntentType.DIM:
        brightness = command.parameters.get("brightness")
        payload = {"brightness_pct": int(brightness)} if brightness is not None else {"brightness_step_pct": -20}
        return "light", "turn_on", "dimmed", payload
    if intent_type == VoiceIntentType.BRIGHTEN:
        brightness = command.parameters.get("brightness")
        payload = {"brightness_pct": int(brightness)} if brightness is not None else {"brightness_step_pct": 20}
        return "light", "turn_on", "brightened", payload
    if intent_type in {VoiceIntentType.CLIMATE_SET, VoiceIntentType.SET_TEMPERATURE}:
        temperature = command.parameters.get("temperature")
        if temperature is None:
            raise ValueError("temperature parameter missing")
        payload = {"temperature": int(temperature)}
        return "climate", "set_temperature", {"temperature": int(temperature)}, payload
    if intent_type == VoiceIntentType.SET_COLOR:
        color = command.parameters.get("color")
        if not color:
            raise ValueError("color parameter missing")
        payload = {"color_name": str(color)}
        return "light", "turn_on", str(color), payload
    raise ValueError(f"voice intent not actionable: {intent_type.value}")


def _build_voice_action(command: ControlVoiceCommand, payload: dict[str, Any]) -> tuple[dict[str, Any], Optional[str], Optional[str]]:
    zone_id = str(payload.get("zone_id") or command.zone_id or "").strip() or None
    module_id = str(payload.get("module_id") or _default_module_id_for_voice_intent(command.intent_type) or "").strip() or None

    target = dict(payload.get("target") or {}) if isinstance(payload.get("target"), dict) else {}
    entity_id = str(payload.get("entity_id") or target.get("entity_id") or command.entity_id or "").strip() or None
    if entity_id is None:
        entity_id = _default_entity_id(module_id, zone_id)
    if entity_id and "entity_id" not in target:
        target["entity_id"] = entity_id

    domain, service, expected_state, action_payload = _voice_action_payload(command.intent_type, command)
    if not module_id:
        inferred = infer_module_id_for_action({
            "domain": domain,
            "service": service,
            "entity_id": entity_id,
            "state": expected_state,
        })
        module_id = str(inferred or "").strip() or None

    action = {
        "domain": str(payload.get("domain") or domain).strip().lower(),
        "service": str(payload.get("service") or service).strip().lower(),
        "entity_id": entity_id,
        "state": expected_state,
        "target": target,
    }
    if action_payload:
        action["payload"] = action_payload
    return action, zone_id, module_id


def _build_voice_explanation(command: ControlVoiceCommand, action: dict[str, Any]) -> str:
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    entity_id = str(action.get("entity_id") or target.get("entity_id") or "").strip()
    action_type = ".".join(
        part for part in (action.get("domain"), action.get("service")) if isinstance(part, str) and part
    )
    details = []
    if entity_id:
        details.append(entity_id)
    if command.zone_id:
        details.append(str(command.zone_id))
    scope = f" ({', '.join(details)})" if details else ""
    return f"Voice command '{command.raw_text}' resolved to {action_type}{scope}."



def _command_from_dict(payload: dict[str, Any]) -> ControlVoiceCommand:
    """Rehydrate a serialized voice command from dialog responses."""
    return ControlVoiceCommand(
        command_id=str(payload.get("command_id") or "").strip(),
        intent_type=VoiceIntentType(str(payload.get("intent_type") or VoiceIntentType.UNKNOWN.value)),
        language=ControlLanguage(str(payload.get("language") or ControlLanguage.DE.value)),
        raw_text=str(payload.get("raw_text") or ""),
        zone_id=str(payload.get("zone_id") or "").strip() or None,
        module_id=str(payload.get("module_id") or "").strip() or None,
        entity_id=str(payload.get("entity_id") or "").strip() or None,
        parameters=dict(payload.get("parameters") or {}),
        confidence=float(payload.get("confidence") or 0.0),
        timestamp=str(payload.get("timestamp") or _utcnow()),
    )


def _normalize_follow_up_status(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "open").strip().lower()).strip("_") or "open"


def _normalize_resume_follow_up_target(payload: dict[str, Any] | None) -> Optional[dict[str, Any]]:
    if not isinstance(payload, dict):
        return None

    target_kind = str(payload.get("target_kind") or payload.get("kind") or "").strip().lower()
    if target_kind not in {"proposal", "action_closure"}:
        return None

    target_id = str(
        payload.get("target_id")
        or payload.get("proposal_id")
        or payload.get("closure_id")
        or payload.get("id")
        or ""
    ).strip()
    if not target_id:
        return None

    return {
        "target_kind": target_kind,
        "target_id": target_id,
        "zone_id": str(payload.get("zone_id") or "").strip() or None,
        "module_id": str(payload.get("module_id") or "").strip() or None,
        "summary": str(payload.get("summary") or "").strip() or None,
        "status": _normalize_follow_up_status(payload.get("status")),
    }


def _is_follow_up_terminal_status(status: Any) -> bool:
    return _normalize_follow_up_status(status) in {
        "closed",
        "completed",
        "done",
        "executed",
        "resolved",
        "settled",
    }


def _looks_like_follow_up_resume_request(text: str, language: str | None) -> bool:
    return looks_like_follow_up_resume_request(text, language)


def _dialog_session_with_follow_up_override(
    dialog_session: dict[str, Any],
    follow_up_target: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a response-safe dialog payload with an effective follow-up target."""
    session_payload = dict(dialog_session)
    if follow_up_target is None:
        return session_payload

    session_payload["active_follow_up"] = dict(follow_up_target)
    if follow_up_target.get("zone_id"):
        session_payload["current_zone_id"] = follow_up_target["zone_id"]
    return session_payload


def _validate_voice_continue_contract(
    session_id: str,
    dialog_session: dict[str, Any],
    request_text: str,
    request_follow_up_target: dict[str, Any] | None,
) -> Optional[tuple[dict[str, Any], int]]:
    """Reject non-resumable continue calls before mutating dialog state."""
    resumable_target = _normalize_resume_follow_up_target(request_follow_up_target)
    if resumable_target is None:
        resumable_target = _normalize_resume_follow_up_target(
            dialog_session.get("active_follow_up") if isinstance(dialog_session.get("active_follow_up"), dict) else None
        )

    effective_dialog_session = _dialog_session_with_follow_up_override(dialog_session, resumable_target)

    if resumable_target is not None and _is_follow_up_terminal_status(resumable_target.get("status")):
        return {
            "status": "error",
            "dialog_phase": "resume_conflict",
            "message": f"Voice control follow-up target already closed: {resumable_target['target_id']}",
            "dialog_session": effective_dialog_session,
            "follow_up_target": resumable_target,
        }, 409

    dialog_status = str(dialog_session.get("status") or "").strip().lower()
    if dialog_status == "resolved" and resumable_target is None:
        return {
            "status": "error",
            "dialog_phase": "resume_conflict",
            "message": f"Voice control session already resolved: {session_id}",
            "dialog_session": dialog_session,
        }, 409

    if dialog_status == "resolved" and resumable_target is not None:
        if not _looks_like_follow_up_resume_request(request_text, dialog_session.get("language")):
            return {
                "status": "error",
                "dialog_phase": "resume_conflict",
                "message": (
                    "Voice control follow-up resume requires explicit follow-up phrasing "
                    f"for target {resumable_target['target_id']}"
                ),
                "dialog_session": effective_dialog_session,
                "follow_up_target": resumable_target,
            }, 409

    return None


def _store_voice_proposal(proposal: dict[str, Any]) -> None:
    _get_voice_control_proposals()[str(proposal.get("proposal_id") or "").strip()] = dict(proposal)


def _load_voice_proposal(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    inline = payload.get("proposal")
    if isinstance(inline, dict):
        return dict(inline)

    proposal_id = str(payload.get("proposal_id") or "").strip()
    if not proposal_id:
        return None
    stored = _get_voice_control_proposals().get(proposal_id)
    return dict(stored) if isinstance(stored, dict) else None


def _materialize_voice_confirmation_response(proposal: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    proposal_id = str(proposal.get("proposal_id") or "").strip()
    zone_id = str(payload.get("zone_id") or proposal.get("zone_id") or "").strip()
    action = proposal.get("action") if isinstance(proposal.get("action"), dict) else {}
    if not proposal_id or not zone_id or not action:
        raise ValueError("proposal_id, zone_id, and action are required")

    zone_type = _normalize_zone_type(payload.get("zone_type") or proposal.get("zone_type"))
    module_id = str(
        payload.get("module_id")
        or proposal.get("module_id")
        or infer_module_id_for_action(action)
        or ""
    ).strip() or None

    module_overrides = payload.get("module_overrides") if isinstance(payload.get("module_overrides"), dict) else proposal.get("module_overrides")
    module_override = (
        payload.get("module_override")
        if isinstance(payload.get("module_override"), dict)
        else resolve_module_override_for_action(zone_type, module_id, module_overrides)
    )
    explicit_styx_instruction = bool(payload.get("styx_instruction") or payload.get("execute_now"))
    policy_gate = evaluate_action_policy(
        module_id,
        module_override,
        explicit_styx_instruction=explicit_styx_instruction,
    )

    accepted_at = _utcnow()
    action_preview = _build_service_call_preview(action)
    action_seed = f"{proposal_id}|{zone_id}|{module_id or 'unknown'}|voice"
    action_intent_id = f"action:{hashlib.sha1(action_seed.encode('utf-8')).hexdigest()[:12]}"

    proposal_intent = {
        "contract": "ProposalIntentV1",
        "proposal_id": proposal_id,
        "zone_id": zone_id,
        "module_id": module_id,
        "state": "accepted",
        "accepted_at": accepted_at,
        "title": proposal.get("summary") or proposal.get("raw_text"),
        "summary": proposal.get("explanation"),
        "confidence": proposal.get("confidence"),
        "source": "voice.accepted",
    }
    action_intent = {
        "contract": "ActionIntentV1",
        "action_intent_id": action_intent_id,
        "proposal_id": proposal_id,
        "zone_id": zone_id,
        "module_id": module_id,
        "source": "voice.accepted",
        "execution_state": policy_gate["execution_state"],
        "eligible_for_execution": policy_gate["eligible_for_execution"],
        "needs_explicit_styx_instruction": policy_gate["needs_explicit_styx_instruction"],
        "blocked_reasons": policy_gate["blocked_reasons"],
        "accepted_at": accepted_at,
        "action": action_preview,
        "policy": policy_gate,
    }
    habitat_module_command = {
        "contract": "HabitatModuleCommandV1",
        "module_id": module_id,
        "output_adapter": str(module_override.get("output_adapter") or "homeassistant") if isinstance(module_override, dict) else "homeassistant",
        "command_mode": "service_call_ready" if policy_gate["eligible_for_execution"] else "preview_only",
        "service_call": action_preview,
        "blocked_reasons": policy_gate["blocked_reasons"],
    }
    ha_output = wrap_accepted_proposal_action(
        action_id=action_intent_id,
        proposal_id=proposal_id,
        module_id=module_id or "unknown",
        zone_id=zone_id,
        service_call=action_preview,
        confidence=float(proposal.get("confidence") or 0.0),
        explanation=str(proposal.get("explanation") or proposal.get("raw_text") or ""),
        accepted_at=accepted_at,
        source="voice.accepted",
        policy_gate=policy_gate,
    )
    action_closure = get_action_closure_store().upsert(
        source="voice.accepted",
        proposal_id=proposal_id,
        action_id=action_intent_id,
        proposal_intent=proposal_intent,
        action_intent=action_intent,
        zone_id=zone_id,
        module_id=module_id,
        service_call=action_preview,
        policy_gate=policy_gate,
        accepted_at=accepted_at,
        metadata={
            "surface": "voice",
            "voice_command_id": str((proposal.get("voice_command") or {}).get("command_id") or "").strip() or None,
        },
    )

    return {
        "status": "ok",
        "proposal": proposal,
        "voice_command": proposal.get("voice_command"),
        "voice_response": proposal.get("voice_response"),
        "proposal_intent": proposal_intent,
        "action_intent": action_intent,
        "action_closure": action_closure,
        "habitat_module_command": habitat_module_command,
        "ha_output": ha_output,
        "policy_gate": policy_gate,
    }


def _handle_voice_control_parse_request(
    data: dict[str, Any],
    *,
    require_existing_session: bool = False,
) -> tuple[dict[str, Any], int]:
    """Materialize the voice control parse/continue contract.

    `/control/parse` can start or continue a session implicitly, while
    `/control/continue` requires an existing `session_id` and makes the
    clarification/continuation hop explicit on the API surface.
    """
    text = str(data.get("text") or "").strip()
    if not text:
        return {"status": "error", "message": "Missing 'text' in request body"}, 400

    try:
        language = _normalize_voice_language(data.get("language"))
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}, 400

    try:
        zone_type = _normalize_zone_type(data.get("zone_type"))
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}, 400

    raw_session_id = str(data.get("session_id") or "").strip()
    if require_existing_session and not raw_session_id:
        return {"status": "error", "message": "Missing 'session_id' in request body"}, 400

    session_id = raw_session_id or "default"
    engine = _get_voice_control_engine()
    dialog_session = engine.get_dialog_session(session_id)
    if require_existing_session and dialog_session is None:
        return {
            "status": "error",
            "message": f"Unknown voice control session: {session_id}",
        }, 404
    if require_existing_session and dialog_session is not None:
        continue_error = _validate_voice_continue_contract(
            session_id,
            dialog_session,
            text,
            data.get("follow_up_target") if isinstance(data.get("follow_up_target"), dict) else None,
        )
        if continue_error is not None:
            return continue_error

    dialog_result = engine.process_dialog_turn(
        text,
        session_id=session_id,
        language=language,
        follow_up_target=data.get("follow_up_target") if isinstance(data.get("follow_up_target"), dict) else None,
    )
    command_payload = dict(dialog_result["command"])
    response_payload = dict(dialog_result["response"])
    dialog_payload = dict(dialog_result["dialog"])
    response_action = response_payload.get("action_taken") if isinstance(response_payload.get("action_taken"), dict) else {}

    if dialog_payload.get("status") == "awaiting_clarification":
        return {
            "status": "ok",
            "dialog_phase": "clarification_needed",
            "proposal": None,
            "voice_command": command_payload,
            "voice_response": response_payload,
            "dialog": dialog_payload,
            "dialog_session": dialog_payload,
            "policy_preview": None,
        }, 200

    if response_action.get("intent") == "dialog_follow_up":
        return {
            "status": "ok",
            "dialog_phase": "follow_up",
            "proposal": None,
            "voice_command": command_payload,
            "voice_response": response_payload,
            "dialog": dialog_payload,
            "dialog_session": dialog_payload,
            "policy_preview": None,
        }, 200

    command = _command_from_dict(command_payload)

    try:
        action, zone_id, module_id = _build_voice_action(command, data)
    except ValueError as exc:
        return {
            "status": "error",
            "message": str(exc),
            "voice_command": command_payload,
            "voice_response": response_payload,
            "dialog": dialog_payload,
            "dialog_session": dialog_payload,
        }, 422

    module_overrides = data.get("module_overrides") if isinstance(data.get("module_overrides"), dict) else None
    module_override = (
        data.get("module_override")
        if isinstance(data.get("module_override"), dict)
        else resolve_module_override_for_action(zone_type, module_id, module_overrides)
    )
    policy_preview = evaluate_action_policy(module_id, module_override, explicit_styx_instruction=False)

    proposal_seed = f"{command.command_id}|{command.raw_text}|{zone_id or 'unassigned'}|{module_id or 'unknown'}"
    proposal_id = f"voice-proposal:{hashlib.sha1(proposal_seed.encode('utf-8')).hexdigest()[:12]}"
    explanation = _build_voice_explanation(command, action)
    proposal = {
        "contract": "VoiceControlProposalV1",
        "proposal_id": proposal_id,
        "source": "voice.control",
        "raw_text": command.raw_text,
        "language": command.language.value,
        "zone_id": zone_id,
        "zone_type": zone_type.value if zone_type is not None else None,
        "module_id": module_id,
        "voice_command": command_payload,
        "voice_response": response_payload,
        "dialog": dialog_payload,
        "action": action,
        "action_preview": _build_service_call_preview(action),
        "confidence": command.confidence,
        "requires_confirmation": bool(response_payload.get("requires_confirmation") or policy_preview["needs_explicit_styx_instruction"]),
        "policy_gate_required": True,
        "explanation": explanation,
        "generated_at": _utcnow(),
    }
    if module_overrides:
        proposal["module_overrides"] = module_overrides
    if isinstance(module_override, dict):
        proposal["module_override"] = dict(module_override)

    _store_voice_proposal(proposal)

    return {
        "status": "ok",
        "dialog_phase": "proposal_ready",
        "proposal": proposal,
        "voice_command": command_payload,
        "voice_response": response_payload,
        "dialog": dialog_payload,
        "dialog_session": dialog_payload,
        "policy_preview": policy_preview,
    }, 200


@bp.route("/control/parse", methods=["POST"])
def parse_voice_control():
    """Parse a voice command into the canonical proposal surface."""
    try:
        data = request.get_json(silent=True) or {}
        body, status_code = _handle_voice_control_parse_request(data)
        return jsonify(body), status_code
    except Exception as e:
        _LOGGER.exception("Voice control parse failed")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/control/continue", methods=["POST"])
def continue_voice_control():
    """Continue an existing voice control dialog session explicitly."""
    try:
        data = request.get_json(silent=True) or {}
        body, status_code = _handle_voice_control_parse_request(data, require_existing_session=True)
        return jsonify(body), status_code
    except Exception as e:
        _LOGGER.exception("Voice control continuation failed")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/control/confirm", methods=["POST"])
def confirm_voice_control():
    """Accept a parsed voice proposal and materialize the policy-gated action handoff."""
    try:
        data = request.get_json(silent=True) or {}
        proposal = _load_voice_proposal(data)
        if not isinstance(proposal, dict):
            return jsonify({"status": "error", "message": "Unknown or missing voice proposal"}), 404

        try:
            body = _materialize_voice_confirmation_response(proposal, data)
        except ValueError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        return jsonify(body)
    except Exception as e:
        _LOGGER.exception("Voice control confirmation failed")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/control/session/<session_id>", methods=["GET"])
def get_voice_control_session(session_id: str):
    """Return the current dialog session state for a voice control conversation."""
    try:
        session = _get_voice_control_engine().get_dialog_session(session_id)
        if session is None:
            return jsonify({
                "status": "error",
                "message": f"Unknown voice control session: {session_id}",
            }), 404

        return jsonify({
            "status": "ok",
            "session": session,
        })
    except Exception as e:
        _LOGGER.exception("Voice control session lookup failed")
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/intent", methods=["POST"])
def process_intent():
    """Process voice intent and return response.
    
    Request body:
    {
        "text": "Mach das Licht an",
        "language": "de",  // optional, auto-detected if not provided
        "zone": "wohnzimmer",  // optional, current zone
        "context": {...},  // optional, existing context
    }
    
    Response:
    {
        "status": "ok",
        "intent": {
            "intent_type": "light_on",
            "confidence": 0.95,
            "slots": {},
            "language": "de",
        },
        "response": {
            "tts_text": "Entspannt. Alles klar, ich mache das. Licht ist an.",
            "actions": [
                {
                    "domain": "light",
                    "service": "turn_on",
                    "entity_id": "light.wohnzimmer"
                }
            ],
            "mood_context": "relax",
            "language": "de",
            "suggestions": ["Möchtest du eine Entspannungs-Playlist?"]
        }
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        
        text = data.get("text")
        if not text:
            return jsonify({
                "status": "error",
                "message": "Missing 'text' in request body"
            }), 400
        
        language = data.get("language")
        zone = data.get("zone")
        
        # Get handler and parse intent
        handler = _get_intent_handler()
        intent = handler.parse_intent(text, language)
        
        # Build or use existing context
        context_builder = _get_context_builder()
        
        if "context" in data and isinstance(data["context"], dict):
            # Use provided context (simplified reconstruction)
            context = context_builder.build_context(
                mood_engine=handler.mood_engine,
                habitus_service=handler.habitus_service,
                zone_name=zone,
                force_refresh=True,
            )
        else:
            # Build fresh context
            context = context_builder.build_context(
                mood_engine=handler.mood_engine,
                habitus_service=handler.habitus_service,
                zone_name=zone,
                force_refresh=data.get("force_context", False),
            )
        
        # Handle intent
        response = handler.handle_intent(intent, context)
        
        return jsonify({
            "status": "ok",
            "intent": intent.to_dict(),
            "response": response.to_dict(),
            "context": context.to_dict(),
        })
    
    except Exception as e:
        _LOGGER.exception("Voice intent processing failed")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/context", methods=["GET"])
def get_context():
    """Get current voice context.
    
    Query parameters:
    - zone: Optional zone name (default: auto-detect)
    - force: Force refresh (default: false)
    
    Response:
    {
        "status": "ok",
        "context": {
            "mood": {
                "state": "relax",
                "confidence": 0.85,
                "reasons": ["Media playing in dark environment"]
            },
            "time": {
                "time_of_day": "evening",
                "day_type": "weekday",
                "hour": 20,
                "is_quiet_hours": false,
                "description_de": "Guten Abend"
            },
            "zone": {
                "zone_name": "wohnzimmer",
                "zone_type": "living_room",
                "is_occupied": true,
                "occupancy_confidence": 0.9
            },
            "active_devices": [...],
            "language_preference": "de"
        }
    }
    """
    try:
        zone = request.args.get("zone")
        force = request.args.get("force", "false").lower() == "true"
        
        context_builder = _get_context_builder()
        handler = _get_intent_handler()
        
        context = context_builder.build_context(
            mood_engine=handler.mood_engine,
            habitus_service=handler.habitus_service,
            zone_name=zone,
            force_refresh=force,
        )
        
        return jsonify({
            "status": "ok",
            "context": context.to_dict(),
        })
    
    except Exception as e:
        _LOGGER.exception("Failed to get voice context")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/hints", methods=["GET"])
def get_hints():
    """Get proactive voice hints.
    
    Query parameters:
    - zone: Optional zone name
    - priority: Filter by minimum priority (low, medium, high, critical)
    - force: Force generation (ignore cooldowns)
    - type: Filter by hint type
    
    Response:
    {
        "status": "ok",
        "hints": [
            {
                "hint_type": "mood_change",
                "priority": "medium",
                "title_de": "Entspannte Stimmung erkannt",
                "title_en": "Relaxed mood detected",
                "message_de": "Die Stimmung ist entspannt. Möchtest du eine Chill-Playlist?",
                "message_en": "The mood is relaxed. Would you like a chill playlist?",
                "suggested_action": {...},
                "context": {...}
            }
        ],
        "critical_count": 0,
        "queued_count": 1
    }
    """
    try:
        zone = request.args.get("zone")
        priority = request.args.get("priority")
        force = request.args.get("force", "false").lower() == "true"
        hint_type = request.args.get("type")
        
        # Get proactive hints
        hints_service = _get_proactive_hints()
        context_builder = _get_context_builder()
        handler = _get_intent_handler()
        
        context = context_builder.build_context(
            mood_engine=handler.mood_engine,
            habitus_service=handler.habitus_service,
            zone_name=zone,
        )
        
        # Generate hints
        all_hints = hints_service.generate_hints(context, force=force)
        
        # Filter by priority
        if priority:
            priority_map = {
                "low": HintPriority.LOW,
                "medium": HintPriority.MEDIUM,
                "high": HintPriority.HIGH,
                "critical": HintPriority.CRITICAL,
            }
            min_priority = priority_map.get(priority.lower(), HintPriority.LOW)
            priority_order = {
                HintPriority.LOW: 0,
                HintPriority.MEDIUM: 1,
                HintPriority.HIGH: 2,
                HintPriority.CRITICAL: 3,
            }
            all_hints = [
                h for h in all_hints
                if priority_order[h.priority] >= priority_order[min_priority]
            ]
        
        # Filter by type
        if hint_type:
            from copilot_core.voice.proactive import HintType
            try:
                filter_type = HintType(hint_type)
                all_hints = [h for h in all_hints if h.hint_type == filter_type]
            except ValueError:
                pass
        
        # Count by priority
        critical_count = sum(1 for h in all_hints if h.priority == HintPriority.CRITICAL)
        queued_count = len(all_hints) - critical_count
        
        return jsonify({
            "status": "ok",
            "hints": [h.to_dict() for h in all_hints],
            "critical_count": critical_count,
            "queued_count": queued_count,
        })
    
    except Exception as e:
        _LOGGER.exception("Failed to get voice hints")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/speak", methods=["POST"])
def generate_speech():
    """Generate TTS response for voice output.
    
    Request body:
    {
        "text": "Licht ist an",
        "language": "de",  // optional
        "mood": "relax",  // optional, for tone adjustment
        "format": "mp3"  // optional: mp3, wav, ogg
    }
    
    Response:
    {
        "status": "ok",
        "audio_url": "/api/v1/voice/audio/abc123",
        "text": "Licht ist an",
        "language": "de",
        "duration_seconds": 1.5
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        
        text = data.get("text")
        if not text:
            return jsonify({
                "status": "error",
                "message": "Missing 'text' in request body"
            }), 400
        
        language = data.get("language", "de")
        audio_format = data.get("format", "mp3")
        
        # Use Styx TTS endpoint if available, otherwise generate a reference ID
        audio_id = f"tts_{hash(text) % 100000}"
        
        return jsonify({
            "status": "ok",
            "audio_url": f"/api/v1/voice/audio/{audio_id}",
            "text": text,
            "language": language,
            "format": audio_format,
            "duration_seconds": len(text) / 15.0,  # Rough estimate
        })
    
    except Exception as e:
        _LOGGER.exception("Failed to generate speech")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/status", methods=["GET"])
def get_status():
    """Get voice system status.
    
    Response:
    {
        "status": "ok",
        "version": "1.0.0",
        "components": {
            "intent_handler": "available",
            "context_builder": "available",
            "proactive_hints": "available",
            "mood_engine": "available",
            "habitus_service": "unavailable"
        },
        "config": {
            "default_language": "de",
            "supported_languages": ["de", "en"],
            "hint_cooldown_seconds": 300,
            "max_hints_per_hour": 6
        }
    }
    """
    try:
        # Check component availability
        components = {}
        
        try:
            handler = _get_intent_handler()
            components["intent_handler"] = "available"
            components["mood_engine"] = "available" if handler.mood_engine else "unavailable"
            components["habitus_service"] = "available" if handler.habitus_service else "unavailable"
        except Exception:
            components["intent_handler"] = "unavailable"
        
        try:
            _get_context_builder()
            components["context_builder"] = "available"
        except Exception:
            components["context_builder"] = "unavailable"
        
        try:
            _get_proactive_hints()
            components["proactive_hints"] = "available"
        except Exception:
            components["proactive_hints"] = "unavailable"
        
        # Get config from proactive hints
        hints_service = _get_proactive_hints()
        config = hints_service.config
        
        return jsonify({
            "status": "ok",
            "version": "1.0.0",
            "components": components,
            "config": {
                "default_language": "de",
                "supported_languages": ["de", "en"],
                "hint_cooldown_seconds": config.hint_cooldown_seconds,
                "max_hints_per_hour": config.max_hints_per_hour,
                "min_priority": config.min_priority.value,
            },
        })
    
    except Exception as e:
        _LOGGER.exception("Failed to get voice status")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/zones", methods=["GET"])
def get_zones():
    """Get available zones for voice context.
    
    Response:
    {
        "status": "ok",
        "zones": [
            {
                "name": "wohnzimmer",
                "type": "living_room",
                "aliases": ["wohnzimmer", "wohn", "lounge"],
                "default_action": "Licht anpassen"
            },
            ...
        ]
    }
    """
    try:
        from copilot_core.voice.context_builder import VoiceContextBuilder
        
        zones = []
        zone_aliases = getattr(VoiceContextBuilder, "ZONE_ALIASES", {})
        for zone_name, zone_type in VoiceContextBuilder.ZONE_TYPE_MAP.items():
            zones.append({
                "name": zone_name,
                "type": zone_type,
                "aliases": zone_aliases.get(zone_name, [zone_name]),
            })
        
        return jsonify({
            "status": "ok",
            "zones": zones,
        })
    
    except Exception as e:
        _LOGGER.exception("Failed to get zones")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/intents", methods=["GET"])
def get_supported_intents():
    """Get list of supported voice intents.
    
    Response:
    {
        "status": "ok",
        "intents": [
            {
                "type": "light_on",
                "description_de": "Licht einschalten",
                "description_en": "Turn on light",
                "examples_de": ["Mach das Licht an", "Licht an"],
                "examples_en": ["Turn on the light", "Light on"]
            },
            ...
        ]
    }
    """
    try:
        from copilot_core.voice.voice_handler import IntentType
        
        intent_info = {
            IntentType.LIGHT_ON: {
                "description_de": "Licht einschalten",
                "description_en": "Turn on light",
                "examples_de": ["Mach das Licht an", "Licht an", "Schalte das Licht ein"],
                "examples_en": ["Turn on the light", "Light on", "Switch the light on"],
            },
            IntentType.LIGHT_OFF: {
                "description_de": "Licht ausschalten",
                "description_en": "Turn off light",
                "examples_de": ["Mach das Licht aus", "Licht aus"],
                "examples_en": ["Turn off the light", "Light off"],
            },
            IntentType.LIGHT_DIM: {
                "description_de": "Licht dimmen",
                "description_en": "Dim light",
                "examples_de": ["Dimm das Licht", "Mach das Licht dunkler"],
                "examples_en": ["Dim the light", "Make the light darker"],
            },
            IntentType.CLIMATE_SET: {
                "description_de": "Temperatur einstellen",
                "description_en": "Set temperature",
                "examples_de": ["Stell die Temperatur auf 21 Grad", "Heiz auf 22 Grad"],
                "examples_en": ["Set temperature to 21 degrees", "Heat to 22 degrees"],
            },
            IntentType.MEDIA_PLAY: {
                "description_de": "Musik abspielen",
                "description_en": "Play music",
                "examples_de": ["Spiel Musik", "Starte Musik"],
                "examples_en": ["Play music", "Start music"],
            },
            IntentType.MEDIA_PAUSE: {
                "description_de": "Musik pausieren",
                "description_en": "Pause music",
                "examples_de": ["Pause", "Musik pause"],
                "examples_en": ["Pause", "Pause music"],
            },
            IntentType.MEDIA_STOP: {
                "description_de": "Musik stoppen",
                "description_en": "Stop music",
                "examples_de": ["Stopp", "Musik aus"],
                "examples_en": ["Stop", "Stop music"],
            },
            IntentType.STATUS_QUERY: {
                "description_de": "Status abfragen",
                "description_en": "Query status",
                "examples_de": ["Wie ist der Status", "Was läuft"],
                "examples_en": ["What's the status", "What's happening"],
            },
            IntentType.MOOD_QUERY: {
                "description_de": "Stimmung abfragen",
                "description_en": "Query mood",
                "examples_de": ["Wie ist die Stimmung", "Stimmungsbericht"],
                "examples_en": ["How's the mood", "What's the atmosphere"],
            },
            IntentType.TIME_QUERY: {
                "description_de": "Uhrzeit abfragen",
                "description_en": "Query time",
                "examples_de": ["Wie viel Uhr ist es", "Wie spät ist es"],
                "examples_en": ["What time is it", "Time"],
            },
        }
        
        intents = []
        for intent_type in IntentType:
            info = intent_info.get(intent_type, {
                "description_de": intent_type.value,
                "description_en": intent_type.value,
                "examples_de": [],
                "examples_en": [],
            })
            intents.append({
                "type": intent_type.value,
                **info,
            })
        
        return jsonify({
            "status": "ok",
            "intents": intents,
        })
    
    except Exception as e:
        _LOGGER.exception("Failed to get supported intents")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# Register blueprint with app
def init_voice_api(app):
    """Initialize voice API endpoints."""
    app.register_blueprint(bp)
    _LOGGER.info("Voice API endpoints registered")
