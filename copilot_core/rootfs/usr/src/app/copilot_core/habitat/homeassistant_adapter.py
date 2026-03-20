"""Home Assistant habitat adapter helpers for Core outbound payloads."""

from __future__ import annotations

from typing import Any, Mapping

from .contracts import (
    VALID_AUTONOMY_MODES,
    ActionIntent,
    HabitatModuleCommand,
    ProposalIntent,
)

ADAPTER_ID = "homeassistant"
OUTBOUND_CONTRACT_VERSION = "ha.output.v1"


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


def _entity_domain(entity_id: Any) -> str | None:
    if isinstance(entity_id, str) and "." in entity_id:
        return entity_id.split(".", 1)[0]
    return None


def _zone_id(data: Mapping[str, Any]) -> str | None:
    if isinstance(data.get("zone_id"), str) and data.get("zone_id"):
        return str(data["zone_id"])
    zone_ids = data.get("zone_ids")
    if isinstance(zone_ids, list):
        for zone_id in zone_ids:
            if isinstance(zone_id, str) and zone_id:
                return zone_id
    return None


def _coerce_autonomy_mode(value: Any, default: str = "learning") -> str:
    if isinstance(value, str) and value in VALID_AUTONOMY_MODES:
        return value
    return default


def _extract_target_payload(data: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    target = _copy_dict(data.get("target") if isinstance(data.get("target"), Mapping) else None)
    payload = _copy_dict(data.get("payload") if isinstance(data.get("payload"), Mapping) else None)

    entity_id = data.get("entity_id") or data.get("target_entity")
    if isinstance(entity_id, str) and entity_id and "entity_id" not in target:
        target["entity_id"] = entity_id

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

    if not payload and isinstance(data.get("service_data"), Mapping):
        payload = _copy_dict(data.get("service_data"))

    return target, payload


def _extract_action_type(data: Mapping[str, Any], target: Mapping[str, Any]) -> str:
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
        if isinstance(first_action.get("service_name"), str) and first_action.get("service_name"):
            return str(first_action["service_name"])

    domain = None
    if isinstance(target.get("entity_id"), str):
        domain = _entity_domain(target.get("entity_id"))
    if not domain and isinstance(data.get("domain"), str):
        domain = str(data["domain"])

    kind = data.get("kind") or data.get("type") or "command"
    if isinstance(kind, str) and kind:
        return f"{domain}.{kind}" if domain else kind
    return f"{domain}.command" if domain else "homeassistant.command"


def _module_id(data: Mapping[str, Any], action_type: str, target: Mapping[str, Any]) -> str:
    raw = data.get("module_id")
    if isinstance(raw, str) and raw:
        return raw
    entity_id = target.get("entity_id")
    dom = _entity_domain(entity_id)
    if dom:
        return dom
    if "." in action_type:
        return action_type.split(".", 1)[0]
    return ADAPTER_ID


def _explanation(data: Mapping[str, Any]) -> str:
    for key in ("explanation", "reason", "description"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _title(data: Mapping[str, Any], action_type: str) -> str:
    for key in ("title", "alias", "name"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return action_type


def _summary(data: Mapping[str, Any], title: str) -> str:
    for key in ("summary", "description", "reason"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return title


def build_proposal_intent(suggestion: Mapping[str, Any]) -> ProposalIntent:
    target, payload = _extract_target_payload(suggestion)
    action_type = _extract_action_type(suggestion, target)
    title = _title(suggestion, action_type)
    summary = _summary(suggestion, title)
    return ProposalIntent(
        module_id=_module_id(suggestion, action_type, target),
        action_type=action_type,
        title=title,
        summary=summary,
        zone_id=_zone_id(suggestion),
        target=target,
        payload=payload,
        confidence=_coerce_float(suggestion.get("confidence") or suggestion.get("score"), 0.0),
        explanation=_explanation(suggestion),
        suggestion_mode=str(suggestion.get("suggestion_mode") or "explainable_manual"),
        autonomy_mode=_coerce_autonomy_mode(suggestion.get("autonomy_mode")),
        direct_execution_enabled=_coerce_bool(suggestion.get("direct_execution_enabled"), False),
        approval_required=_coerce_bool(suggestion.get("approval_required"), True),
        explanation_required=_coerce_bool(suggestion.get("explanation_required"), True),
        requires_confirmation=_coerce_bool(suggestion.get("requires_confirmation"), True),
        output_adapter=ADAPTER_ID,
        source_input_ids=_copy_list(suggestion.get("source_input_ids") if isinstance(suggestion.get("source_input_ids"), list) else None),
        source_event_ids=_copy_list(suggestion.get("source_event_ids") if isinstance(suggestion.get("source_event_ids"), list) else None),
        evidence=_copy_dict(suggestion.get("evidence") if isinstance(suggestion.get("evidence"), Mapping) else None),
        metadata={"raw_suggestion": dict(suggestion)},
    )


def build_action_intent(payload: Mapping[str, Any]) -> ActionIntent:
    target, action_payload = _extract_target_payload(payload)
    action_type = _extract_action_type(payload, target)
    proposal_id = payload.get("proposal_id") if isinstance(payload.get("proposal_id"), str) else None
    action_id = payload.get("action_id") if isinstance(payload.get("action_id"), str) else None
    kwargs: dict[str, Any] = {
        "module_id": _module_id(payload, action_type, target),
        "action_type": action_type,
        "proposal_id": proposal_id,
        "zone_id": _zone_id(payload),
        "target": target,
        "payload": action_payload,
        "confidence": _coerce_float(payload.get("confidence") or payload.get("score"), 0.0),
        "explanation": _explanation(payload),
        "suggestion_mode": str(payload.get("suggestion_mode") or "explainable_manual"),
        "autonomy_mode": _coerce_autonomy_mode(payload.get("autonomy_mode")),
        "direct_execution_enabled": _coerce_bool(payload.get("direct_execution_enabled"), False),
        "approval_required": _coerce_bool(payload.get("approval_required"), True),
        "explanation_required": _coerce_bool(payload.get("explanation_required"), True),
        "requires_confirmation": _coerce_bool(payload.get("requires_confirmation"), True),
        "output_adapter": ADAPTER_ID,
        "source_input_ids": _copy_list(payload.get("source_input_ids") if isinstance(payload.get("source_input_ids"), list) else None),
        "source_event_ids": _copy_list(payload.get("source_event_ids") if isinstance(payload.get("source_event_ids"), list) else None),
        "evidence": _copy_dict(payload.get("evidence") if isinstance(payload.get("evidence"), Mapping) else None),
        "metadata": {"raw_payload": dict(payload)},
        "approved": _coerce_bool(payload.get("approved"), False),
    }
    if action_id:
        kwargs["action_id"] = action_id
    return ActionIntent(**kwargs)


def normalize_outbound_payload(event_type: str, data: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    normalized.setdefault(
        "adapter",
        {
            "name": ADAPTER_ID,
            "direction": "core_to_homeassistant",
            "contract_version": OUTBOUND_CONTRACT_VERSION,
            "event_type": event_type,
        },
    )

    if event_type == "suggestion":
        proposal = build_proposal_intent(data)
        normalized.setdefault("proposal_intent", proposal.to_dict())
        normalized.setdefault(
            "module_command",
            HabitatModuleCommand.from_proposal_intent(proposal).to_dict(),
        )
    elif event_type in {"autonomy_executed", "action", "execute"}:
        action = build_action_intent(data)
        normalized.setdefault("action_intent", action.to_dict())
        normalized.setdefault("module_command", action.to_module_command().to_dict())

    return normalized


__all__ = [
    "ADAPTER_ID",
    "OUTBOUND_CONTRACT_VERSION",
    "build_proposal_intent",
    "build_action_intent",
    "normalize_outbound_payload",
]
