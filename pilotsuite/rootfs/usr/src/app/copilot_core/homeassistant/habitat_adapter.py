"""HomeAssistant Habitat Adapter — HA↔Core Contract Boundary.

Keeps the HA↔Core boundary explicit:
- INBOUND: normalizes HA events → Core NeuronInput / HabitatEvent
- OUTBOUND: normalizes Core proposal/action payloads → HA service commands

This adapter is the Core-side counterpart to the HA-side habitat_adapter.
It ensures that regardless of which end initiates, data crossing the
boundary is wrapped in a canonical contract envelope.

Contract versions:
- INBOUND:  ha.input.v1   (HA → Core)
- OUTBOUND: ha.output.v1   (Core → HA)

See also: HA_CORE_INGEST_CONTRACT.md
"""
from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

_LOGGER = logging.getLogger(__name__)

__version__ = "0.1.0"

# ── Contract Identity ────────────────────────────────────────────────────────

ADAPTER_ID = "homeassistant"
INBOUND_CONTRACT_VERSION = "ha.input.v1"    # HA → Core
OUTBOUND_CONTRACT_VERSION = "ha.output.v1"  # Core → HA
INPUT_MODEL = "NeuronInputV1"

VALID_AUTONOMY_MODES = frozenset({"autonomous", "learning", "off"})

# ── Primitive Coercion Helpers ────────────────────────────────────────────────

def _copy_dict(value: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return dict(value or {})


def _copy_list(value: list[Any] | tuple[Any, ...] | None = None) -> list[Any]:
    return list(value or [])


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_ms(ts: Any) -> int | None:
    if isinstance(ts, (int, float)):
        return int(ts)
    if isinstance(ts, str):
        numeric = ts.strip()
        if numeric.isdigit():
            return int(numeric)
    return None


def _entity_domain(entity_id: Any) -> str | None:
    if isinstance(entity_id, str) and "." in entity_id:
        return entity_id.split(".", 1)[0]
    return None


def _zone_id(zone_ids: list[str] | None) -> str | None:
    if isinstance(zone_ids, list):
        for zone_id in zone_ids:
            if isinstance(zone_id, str) and zone_id:
                return zone_id
    return None


def _adapter_metadata(direction: str, event_type: str, version: str) -> dict[str, Any]:
    return {
        "name": ADAPTER_ID,
        "direction": direction,
        "contract_version": version,
        "event_type": event_type,
    }


def _coerce_autonomy_mode(value: Any, default: str = "learning") -> str:
    if isinstance(value, str) and value in VALID_AUTONOMY_MODES:
        return value
    return default


# ── Inbound: HA → Core ─────────────────────────────────────────────────────────

def build_state_changed_forward_item(
    *,
    item_id: str,
    ts: str,
    entity_id: str,
    old_state: Any,
    new_state: Any,
    zone_ids: list[str] | None = None,
    state_attributes: Mapping[str, Any] | None = None,
    neuron_tags: list[str] | None = None,
    occurred_at_ms: int | None = None,
) -> dict[str, Any]:
    """Build a normalized forward item for a HA state_changed event.

    Produces a dual-structure payload:
    - habitat_event: raw event envelope for the habitat event pipeline
    - neuron_input: structured input for the neuron pipeline

    Args:
        item_id:       Unique event identifier
        ts:            ISO timestamp string
        entity_id:     HomeAssistant entity ID (e.g. light.living_room)
        old_state:     Previous state value
        new_state:     New state value
        zone_ids:      Associated zone IDs
        state_attributes: Entity attributes dict
        neuron_tags:   Tags to route to specific neurons
        occurred_at_ms: Event timestamp in ms (defaults to item_id timestamp)
    """
    zone_ids = _copy_list(zone_ids)
    neuron_tags = _copy_list(neuron_tags)
    domain = _entity_domain(entity_id) or ADAPTER_ID
    occurred_at_ms = occurred_at_ms if occurred_at_ms is not None else (_coerce_ms(item_id) or 0)

    attrs = {
        "domain": domain,
        "zone_ids": zone_ids,
        "old_state": old_state,
        "new_state": new_state,
        "state_attributes": _copy_dict(state_attributes),
    }
    if neuron_tags:
        attrs["neuron_tags"] = list(neuron_tags)

    habitat_event = {
        "event_id": item_id,
        "module_id": domain,
        "event_type": "state_changed",
        "entity_id": entity_id,
        "zone_id": _zone_id(zone_ids),
        "domain": domain,
        "state": new_state,
        "attributes": dict(attrs),
        "context": {
            "source": "homeassistant",
            "ts": ts,
            "direction": "homeassistant_to_core",
        },
        "tags": list(neuron_tags),
        "raw_event": {},
        "occurred_at_ms": occurred_at_ms,
        "input_model": INPUT_MODEL,
    }

    neuron_input = {
        "input_id": f"nin:{item_id}",
        "input_model": INPUT_MODEL,
        "module_id": domain,
        "source_event_id": item_id,
        "zone_id": _zone_id(zone_ids),
        "entity_id": entity_id,
        "domain": domain,
        "signal": "state_changed",
        "value": new_state,
        "confidence": 1.0,
        "observed_at_ms": occurred_at_ms,
        "context": {
            "source": "homeassistant",
            "ts": ts,
            "event_type": "state_changed",
        },
        "tags": list(neuron_tags),
        "neuron_targets": list(neuron_tags),
        "metadata": {
            "old_state": old_state,
            "new_state": new_state,
            "state_attributes": _copy_dict(state_attributes),
            "zone_ids": list(zone_ids),
        },
    }

    return {
        "id": item_id,
        "ts": ts,
        "type": "state_changed",
        "source": "home_assistant",
        "entity_id": entity_id,
        "attributes": attrs,
        "adapter": _adapter_metadata(
            "homeassistant_to_core", "state_changed", INBOUND_CONTRACT_VERSION
        ),
        "habitat_event": habitat_event,
        "neuron_input": neuron_input,
    }


def build_call_service_forward_item(
    *,
    item_id: str,
    ts: str,
    domain: str,
    service: str,
    entity_ids: list[str],
    zone_ids: list[str] | None = None,
    occurred_at_ms: int | None = None,
) -> dict[str, Any]:
    """Build a normalized forward item for a HA call_service event.

    Args:
        item_id:    Unique event identifier
        ts:         ISO timestamp string
        domain:     HA service domain (e.g. light, climate)
        service:    Service name (e.g. turn_on, set_temperature)
        entity_ids: Target entity IDs
        zone_ids:   Associated zone IDs
        occurred_at_ms: Event timestamp in ms
    """
    entity_ids = [
        eid for eid in entity_ids
        if isinstance(eid, str) and eid
    ]
    zone_ids = _copy_list(zone_ids)
    lead_entity_id = entity_ids[0] if entity_ids else f"{domain}.unknown"
    occurred_at_ms = occurred_at_ms if occurred_at_ms is not None else (_coerce_ms(item_id) or 0)

    attrs = {
        "domain": domain,
        "service": service,
        "entity_ids": list(entity_ids),
        "zone_ids": list(zone_ids),
    }

    habitat_event = {
        "event_id": item_id,
        "module_id": domain or ADAPTER_ID,
        "event_type": "call_service",
        "entity_id": lead_entity_id,
        "zone_id": _zone_id(zone_ids),
        "domain": domain or _entity_domain(lead_entity_id),
        "state": {"domain": domain, "service": service, "entity_ids": list(entity_ids)},
        "attributes": dict(attrs),
        "context": {
            "source": "homeassistant",
            "ts": ts,
            "direction": "homeassistant_to_core",
        },
        "tags": [],
        "raw_event": {},
        "occurred_at_ms": occurred_at_ms,
        "input_model": INPUT_MODEL,
    }

    signal = f"{domain}.{service}" if domain and service else "call_service"

    neuron_input = {
        "input_id": f"nin:{item_id}",
        "input_model": INPUT_MODEL,
        "module_id": domain or ADAPTER_ID,
        "source_event_id": item_id,
        "zone_id": _zone_id(zone_ids),
        "entity_id": lead_entity_id,
        "domain": domain or _entity_domain(lead_entity_id),
        "signal": signal,
        "value": {"domain": domain, "service": service},
        "confidence": 1.0,
        "observed_at_ms": occurred_at_ms,
        "context": {
            "source": "homeassistant",
            "ts": ts,
            "event_type": "call_service",
        },
        "tags": [],
        "neuron_targets": [],
        "metadata": {
            "entity_ids": list(entity_ids),
            "zone_ids": list(zone_ids),
        },
    }

    return {
        "id": item_id,
        "ts": ts,
        "type": "call_service",
        "source": "home_assistant",
        "entity_id": lead_entity_id,
        "attributes": attrs,
        "adapter": _adapter_metadata(
            "homeassistant_to_core", "call_service", INBOUND_CONTRACT_VERSION
        ),
        "habitat_event": habitat_event,
        "neuron_input": neuron_input,
    }


# ── Outbound: Core → HA ───────────────────────────────────────────────────────

def _extract_target_payload(
    data: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Extract target and payload from a Core proposal/action payload."""
    target = _copy_dict(
        data.get("target") if isinstance(data.get("target"), Mapping) else None
    )
    payload = _copy_dict(
        data.get("payload") if isinstance(data.get("payload"), Mapping) else None
    )

    entity_id = data.get("entity_id") or data.get("target_entity")
    if isinstance(entity_id, str) and entity_id and "entity_id" not in target:
        target["entity_id"] = entity_id

    if not payload and isinstance(data.get("service_data"), Mapping):
        payload = _copy_dict(data.get("service_data"))

    actions = data.get("actions")
    first_action = actions[0] if isinstance(actions, list) and actions else None
    if isinstance(first_action, Mapping):
        if not target:
            if isinstance(first_action.get("target"), Mapping):
                target = _copy_dict(first_action.get("target"))
            elif isinstance(first_action.get("entity_id"), str):
                target = {"entity_id": first_action["entity_id"]}
        if not payload:
            if isinstance(first_action.get("service_data"), Mapping):
                payload = _copy_dict(first_action.get("service_data"))
            elif isinstance(first_action.get("data"), Mapping):
                payload = _copy_dict(first_action.get("data"))

    return target, payload


def _extract_action_type(
    data: Mapping[str, Any], target: Mapping[str, Any]
) -> str:
    """Derive the action type string from a Core payload."""
    for key in ("action_type", "service", "service_name"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value

    actions = data.get("actions")
    first_action = actions[0] if isinstance(actions, list) and actions else None
    if isinstance(first_action, Mapping):
        domain = first_action.get("domain")
        service = first_action.get("service")
        if isinstance(domain, str) and isinstance(service, str) and domain and service:
            return f"{domain}.{service}"

    entity_domain = _entity_domain(target.get("entity_id"))
    kind = data.get("kind") or data.get("type") or "command"
    if isinstance(kind, str) and kind:
        return f"{entity_domain}.{kind}" if entity_domain else kind
    return f"{entity_domain}.command" if entity_domain else "homeassistant.command"


def _module_id(
    data: Mapping[str, Any], action_type: str, target: Mapping[str, Any]
) -> str:
    """Determine the module_id for a Core action."""
    raw = data.get("module_id")
    if isinstance(raw, str) and raw:
        return raw
    domain = _entity_domain(target.get("entity_id"))
    if domain:
        return domain
    if "." in action_type:
        return action_type.split(".", 1)[0]
    return ADAPTER_ID


def _zone_from_payload(data: Mapping[str, Any]) -> str | None:
    """Extract zone_id from payload."""
    zone_id = data.get("zone_id")
    if isinstance(zone_id, str) and zone_id:
        return zone_id
    zone_ids = data.get("zone_ids")
    if isinstance(zone_ids, list):
        return _zone_id([z for z in zone_ids if isinstance(z, str)])
    return None


def _build_proposal_intent(data: Mapping[str, Any], action_type: str, target: dict, payload: dict) -> dict[str, Any]:
    """Build a proposal_intent block from Core proposal data."""
    title = str(data.get("title") or data.get("alias") or action_type)
    summary = str(data.get("summary") or data.get("description") or title)
    explanation = str(data.get("explanation") or data.get("reason") or "")

    return {
        "proposal_id": str(
            data.get("proposal_id")
            or f"proposal:{_adapter_metadata('core_to_homeassistant', 'suggestion', OUTBOUND_CONTRACT_VERSION).get('event_type', 'suggestion')}"
        ),
        "module_id": _module_id(data, action_type, target),
        "zone_id": _zone_from_payload(data),
        "action_type": action_type,
        "title": title,
        "summary": summary,
        "target": dict(target),
        "payload": dict(payload),
        "confidence": _coerce_float(data.get("confidence") or data.get("score"), 0.0),
        "explanation": explanation,
        "suggestion_mode": str(data.get("suggestion_mode") or "explainable_manual"),
        "autonomy_mode": _coerce_autonomy_mode(data.get("autonomy_mode")),
        "direct_execution_enabled": _coerce_bool(data.get("direct_execution_enabled"), False),
        "approval_required": _coerce_bool(data.get("approval_required"), True),
        "explanation_required": _coerce_bool(data.get("explanation_required"), True),
        "requires_confirmation": _coerce_bool(data.get("requires_confirmation"), True),
        "output_adapter": ADAPTER_ID,
        "source_input_ids": _copy_list(
            data.get("source_input_ids") if isinstance(data.get("source_input_ids"), list) else None
        ),
        "source_event_ids": _copy_list(
            data.get("source_event_ids") if isinstance(data.get("source_event_ids"), list) else None
        ),
        "evidence": _copy_dict(
            data.get("evidence") if isinstance(data.get("evidence"), Mapping) else None
        ),
        "metadata": {"raw_suggestion": dict(data)},
    }


def _build_module_command_from_proposal(
    proposal_intent: dict[str, Any], data: Mapping[str, Any]
) -> dict[str, Any]:
    """Build a module_command block from a proposal_intent."""
    return {
        "command_id": str(
            data.get("command_id")
            or f"cmd:{proposal_intent['proposal_id']}"
        ),
        "module_id": proposal_intent["module_id"],
        "command_name": proposal_intent["action_type"],
        "zone_id": proposal_intent["zone_id"],
        "proposal_id": proposal_intent["proposal_id"],
        "action_id": None,
        "target": dict(proposal_intent["target"]),
        "payload": dict(proposal_intent["payload"]),
        "command_mode": "suggest",
        "explanation": proposal_intent["explanation"],
        "approved": False,
        "metadata": {
            "title": proposal_intent["title"],
            "summary": proposal_intent["summary"],
            "confidence": proposal_intent["confidence"],
            "suggestion_mode": proposal_intent["suggestion_mode"],
            "autonomy_mode": proposal_intent["autonomy_mode"],
            "direct_execution_enabled": proposal_intent["direct_execution_enabled"],
            "approval_required": proposal_intent["approval_required"],
            "requires_confirmation": proposal_intent["requires_confirmation"],
            "output_adapter": ADAPTER_ID,
        },
    }


def _build_action_intent(
    data: Mapping[str, Any], action_type: str, target: dict, payload: dict
) -> dict[str, Any]:
    """Build an action_intent block from Core action data."""
    approved = _coerce_bool(data.get("approved"), True)
    return {
        "action_id": str(data.get("action_id") or f"action:{data.get('event_type', 'unknown')}"),
        "proposal_id": data.get("proposal_id"),
        "module_id": _module_id(data, action_type, target),
        "zone_id": _zone_from_payload(data),
        "action_type": action_type,
        "target": target,
        "payload": payload,
        "confidence": _coerce_float(data.get("confidence") or data.get("score"), 0.0),
        "explanation": str(data.get("explanation") or data.get("reason") or ""),
        "suggestion_mode": str(data.get("suggestion_mode") or "explainable_manual"),
        "autonomy_mode": _coerce_autonomy_mode(data.get("autonomy_mode")),
        "direct_execution_enabled": _coerce_bool(data.get("direct_execution_enabled"), False),
        "approval_required": _coerce_bool(data.get("approval_required"), True),
        "explanation_required": _coerce_bool(data.get("explanation_required"), True),
        "requires_confirmation": _coerce_bool(data.get("requires_confirmation"), True),
        "execution_state": data.get("execution_state"),
        "decision_source": data.get("decision_source"),
        "blocked_reasons": _copy_list(
            data.get("blocked_reasons") if isinstance(data.get("blocked_reasons"), list) else None
        ),
        "accepted_at": data.get("accepted_at"),
        "source": data.get("source"),
        "output_adapter": ADAPTER_ID,
        "source_input_ids": _copy_list(
            data.get("source_input_ids") if isinstance(data.get("source_input_ids"), list) else None
        ),
        "source_event_ids": _copy_list(
            data.get("source_event_ids") if isinstance(data.get("source_event_ids"), list) else None
        ),
        "evidence": _copy_dict(
            data.get("evidence") if isinstance(data.get("evidence"), Mapping) else None
        ),
        "metadata": {"raw_payload": dict(data)},
        "approved": approved,
    }


def _build_module_command_from_action(
    action_intent: dict[str, Any], data: Mapping[str, Any]
) -> dict[str, Any]:
    """Build a module_command block from an action_intent."""
    return {
        "command_id": str(
            data.get("command_id")
            or f"cmd:{action_intent['action_id']}"
        ),
        "module_id": action_intent["module_id"],
        "command_name": action_intent["action_type"],
        "zone_id": action_intent["zone_id"],
        "proposal_id": action_intent.get("proposal_id"),
        "action_id": action_intent["action_id"],
        "target": dict(action_intent["target"]),
        "payload": dict(action_intent["payload"]),
        "command_mode": "execute" if action_intent["approved"] else "suggest",
        "explanation": action_intent["explanation"],
        "approved": action_intent["approved"],
        "metadata": {
            "confidence": action_intent["confidence"],
            "suggestion_mode": action_intent["suggestion_mode"],
            "autonomy_mode": action_intent["autonomy_mode"],
            "direct_execution_enabled": action_intent["direct_execution_enabled"],
            "approval_required": action_intent["approval_required"],
            "requires_confirmation": action_intent["requires_confirmation"],
            "execution_state": action_intent.get("execution_state"),
            "decision_source": action_intent.get("decision_source"),
            "blocked_reasons": _copy_list(action_intent.get("blocked_reasons")),
            "accepted_at": action_intent.get("accepted_at"),
            "source": action_intent.get("source"),
            "output_adapter": ADAPTER_ID,
        },
    }


def normalize_received_webhook_payload(
    event_type: str, data: Mapping[str, Any]
) -> dict[str, Any]:
    """Normalize a webhook payload received by Core from HA (inbound).

    Or: normalize a Core outbound payload intended for HA (outbound).

    Handles two event_type families:
    - "suggestion": Core → HA suggestion for user approval
    - "autonomy_executed" / "action" / "execute": Core → HA execution command

    The returned dict always has:
    - "adapter": metadata block with direction, contract_version, event_type
    - "proposal_intent" + "module_command" (for suggestions)
    - "action_intent" + "module_command" (for executions)
    - "raw": original data preserved for audit

    Args:
        event_type: One of "suggestion", "autonomy_executed", "action", "execute"
        data:        Raw webhook payload dict

    Returns:
        Normalized dict with contract envelope
    """
    normalized = dict(data)
    normalized.setdefault(
        "adapter",
        _adapter_metadata(
            "core_to_homeassistant", event_type, OUTBOUND_CONTRACT_VERSION
        ),
    )

    if event_type == "suggestion" and "proposal_intent" not in normalized:
        target, payload = _extract_target_payload(data)
        action_type = _extract_action_type(data, target)
        proposal_intent = _build_proposal_intent(data, action_type, target, payload)
        normalized["proposal_intent"] = proposal_intent
        normalized.setdefault(
            "module_command",
            _build_module_command_from_proposal(proposal_intent, data),
        )

    elif event_type in {"autonomy_executed", "action", "execute"} and "action_intent" not in normalized:
        target, payload = _extract_target_payload(data)
        action_type = _extract_action_type(data, target)
        action_intent = _build_action_intent(data, action_type, target, payload)
        normalized["action_intent"] = action_intent
        normalized.setdefault(
            "module_command",
            _build_module_command_from_action(action_intent, data),
        )

    return normalized


# ── Convenience: quick envelope builders ──────────────────────────────────────

def wrap_ha_state_changed(
    item_id: str,
    ts: str,
    entity_id: str,
    old_state: Any,
    new_state: Any,
    zone_ids: list[str] | None = None,
    state_attributes: Mapping[str, Any] | None = None,
    neuron_tags: list[str] | None = None,
) -> dict[str, Any]:
    """Convenience: wrap a HA state_changed event for Core ingestion."""
    return build_state_changed_forward_item(
        item_id=item_id,
        ts=ts,
        entity_id=entity_id,
        old_state=old_state,
        new_state=new_state,
        zone_ids=zone_ids,
        state_attributes=state_attributes,
        neuron_tags=neuron_tags,
    )


def wrap_ha_service_call(
    item_id: str,
    ts: str,
    domain: str,
    service: str,
    entity_ids: list[str],
    zone_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Convenience: wrap a HA call_service event for Core ingestion."""
    return build_call_service_forward_item(
        item_id=item_id,
        ts=ts,
        domain=domain,
        service=service,
        entity_ids=entity_ids,
        zone_ids=zone_ids,
    )


def wrap_core_proposal(
    proposal_id: str,
    module_id: str,
    action_type: str,
    target: dict[str, Any],
    payload: dict[str, Any],
    confidence: float = 0.0,
    explanation: str = "",
    zone_id: str | None = None,
    title: str = "",
    summary: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """Convenience: build a normalized Core → HA proposal envelope."""
    data = {
        "proposal_id": proposal_id,
        "module_id": module_id,
        "action_type": action_type,
        "target": target,
        "payload": payload,
        "confidence": confidence,
        "explanation": explanation,
        "zone_id": zone_id,
        "title": title or action_type,
        "summary": summary or action_type,
        **extra,
    }
    return normalize_received_webhook_payload("suggestion", data)


def wrap_core_action(
    action_id: str,
    module_id: str,
    action_type: str,
    target: dict[str, Any],
    payload: dict[str, Any],
    confidence: float = 1.0,
    explanation: str = "",
    zone_id: str | None = None,
    approved: bool = True,
    proposal_id: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Convenience: build a normalized Core → HA action/execute envelope."""
    data = {
        "action_id": action_id,
        "module_id": module_id,
        "action_type": action_type,
        "target": target,
        "payload": payload,
        "confidence": confidence,
        "explanation": explanation,
        "zone_id": zone_id,
        "approved": approved,
        "proposal_id": proposal_id,
        **extra,
    }
    return normalize_received_webhook_payload("autonomy_executed", data)


def wrap_accepted_proposal_action(
    action_id: str,
    proposal_id: str,
    module_id: str,
    zone_id: str | None,
    service_call: Mapping[str, Any],
    confidence: float = 0.0,
    explanation: str = "",
    policy_gate: Mapping[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a canonical Core → HA action envelope from an accepted proposal preview.

    This hardens the accepted-proposal handoff so API routes can reuse the same
    adapter contract logic instead of rebuilding action_type / target / payload /
    approval semantics ad hoc.
    """
    preview = dict(service_call)
    policy = dict(policy_gate or {})

    domain = str(preview.get("domain") or "").strip().lower()
    service = str(preview.get("service") or "").strip().lower()
    action_type = ".".join(part for part in [domain, service] if part) or "unknown"
    target = dict(preview.get("target") or {})
    payload = dict(preview.get("payload") or {})
    if preview.get("expected_state") is not None and "expected_state" not in payload:
        payload["expected_state"] = preview.get("expected_state")

    approved = _coerce_bool(extra.pop("approved", policy.get("eligible_for_execution")), False)
    needs_explicit = _coerce_bool(
        extra.get("requires_confirmation", policy.get("needs_explicit_styx_instruction")),
        True,
    )
    autonomy_mode = extra.pop(
        "autonomy_mode",
        "autonomous" if approved and not needs_explicit else "learning",
    )
    direct_execution_enabled = _coerce_bool(
        extra.pop("direct_execution_enabled", policy.get("direct_execution_enabled")),
        False,
    )
    approval_required = _coerce_bool(
        extra.pop("approval_required", policy.get("approval_required")),
        True,
    )
    requires_confirmation = _coerce_bool(
        extra.pop("requires_confirmation", policy.get("needs_explicit_styx_instruction")),
        True,
    )
    blocked_reasons = _copy_list(
        extra.pop("blocked_reasons", policy.get("blocked_reasons") if isinstance(policy.get("blocked_reasons"), list) else None)
    )

    return wrap_core_action(
        action_id=action_id,
        proposal_id=proposal_id,
        module_id=module_id,
        action_type=action_type,
        target=target,
        payload=payload,
        confidence=confidence,
        explanation=explanation,
        zone_id=zone_id,
        approved=approved,
        autonomy_mode=autonomy_mode,
        suggestion_mode=str(extra.pop("suggestion_mode", policy.get("suggestion_mode") or "explainable_manual")),
        explanation_required=_coerce_bool(
            extra.pop("explanation_required", policy.get("explanation_required")),
            True,
        ),
        execution_state=extra.pop("execution_state", policy.get("execution_state")),
        decision_source=extra.pop("decision_source", policy.get("decision_source")),
        accepted_at=extra.pop("accepted_at", None),
        source=extra.pop("source", None),
        direct_execution_enabled=direct_execution_enabled,
        approval_required=approval_required,
        requires_confirmation=requires_confirmation,
        blocked_reasons=blocked_reasons,
        **extra,
    )


__all__ = [
    # Identity
    "ADAPTER_ID",
    "INBOUND_CONTRACT_VERSION",
    "OUTBOUND_CONTRACT_VERSION",
    "INPUT_MODEL",
    "VALID_AUTONOMY_MODES",
    # Inbound builders
    "build_state_changed_forward_item",
    "build_call_service_forward_item",
    "wrap_ha_state_changed",
    "wrap_ha_service_call",
    # Outbound normalizer
    "normalize_received_webhook_payload",
    # Outbound convenience builders
    "wrap_core_proposal",
    "wrap_core_action",
    "wrap_accepted_proposal_action",
]
