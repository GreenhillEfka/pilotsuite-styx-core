"""Core habitat-module contracts for normalized inbound and outbound flows.

These dataclasses provide a small, explicit boundary between habitat modules
(e.g. Home Assistant) and the PilotSuite core.

Design goals for v1:
- Keep the contracts lightweight and easy to serialize
- Preserve suggestion-first defaults
- Carry autonomy / approval policy alongside proposals and actions
- Be practical enough for immediate use by adapters and the proposal pipeline
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

DEFAULT_INPUT_MODEL = "NeuronInputV1"
DEFAULT_SUGGESTION_MODE = "explainable_manual"
VALID_AUTONOMY_MODES = frozenset({"autonomous", "learning", "off"})
VALID_COMMAND_MODES = frozenset({"suggest", "execute"})


def _now_ms() -> int:
    return int(time.time() * 1000)


def _make_id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex[:12]}"


def _copy_dict(value: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return dict(value or {})


def _copy_list(value: list[Any] | tuple[Any, ...] | None = None) -> list[Any]:
    return list(value or [])


def _coerce_confidence(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _infer_domain(entity_id: str | None, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    if entity_id and "." in entity_id:
        return entity_id.split(".", 1)[0]
    return None


@dataclass(frozen=True)
class HabitatModuleEvent:
    """Raw-but-structured event emitted by a habitat module.

    This is the adapter-facing input contract before the event is normalized
    into a neuron-friendly core input.
    """

    module_id: str
    event_type: str
    entity_id: str | None = None
    zone_id: str | None = None
    domain: str | None = None
    state: Any = None
    attributes: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    raw_event: dict[str, Any] = field(default_factory=dict)
    occurred_at_ms: int = field(default_factory=_now_ms)
    event_id: str = field(default_factory=lambda: _make_id("hme"))
    input_model: str = DEFAULT_INPUT_MODEL

    def __post_init__(self) -> None:
        if not self.module_id:
            raise ValueError("module_id is required")
        if not self.event_type:
            raise ValueError("event_type is required")
        object.__setattr__(self, "domain", _infer_domain(self.entity_id, self.domain))
        object.__setattr__(self, "attributes", _copy_dict(self.attributes))
        object.__setattr__(self, "context", _copy_dict(self.context))
        object.__setattr__(self, "tags", _copy_list(self.tags))
        object.__setattr__(self, "raw_event", _copy_dict(self.raw_event))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "module_id": self.module_id,
            "event_type": self.event_type,
            "entity_id": self.entity_id,
            "zone_id": self.zone_id,
            "domain": self.domain,
            "state": self.state,
            "attributes": dict(self.attributes),
            "context": dict(self.context),
            "tags": list(self.tags),
            "raw_event": dict(self.raw_event),
            "occurred_at_ms": self.occurred_at_ms,
            "input_model": self.input_model,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HabitatModuleEvent":
        return cls(
            event_id=str(data.get("event_id") or _make_id("hme")),
            module_id=str(data["module_id"]),
            event_type=str(data["event_type"]),
            entity_id=data.get("entity_id"),
            zone_id=data.get("zone_id"),
            domain=data.get("domain"),
            state=data.get("state"),
            attributes=_copy_dict(data.get("attributes")),
            context=_copy_dict(data.get("context")),
            tags=_copy_list(data.get("tags")),
            raw_event=_copy_dict(data.get("raw_event")),
            occurred_at_ms=int(data.get("occurred_at_ms") or _now_ms()),
            input_model=str(data.get("input_model") or DEFAULT_INPUT_MODEL),
        )

    def to_neuron_input(
        self,
        *,
        signal: str | None = None,
        value: Any | None = None,
        confidence: float = 1.0,
        neuron_targets: list[str] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "NeuronInput":
        return NeuronInput(
            module_id=self.module_id,
            input_model=self.input_model,
            source_event_id=self.event_id,
            zone_id=self.zone_id,
            entity_id=self.entity_id,
            domain=self.domain,
            signal=signal or self.event_type,
            value=self.state if value is None else value,
            confidence=confidence,
            observed_at_ms=self.occurred_at_ms,
            context={**self.context, "event_type": self.event_type},
            tags=list(self.tags),
            neuron_targets=list(neuron_targets or []),
            metadata={**self.attributes, **_copy_dict(metadata)},
        )


@dataclass(frozen=True)
class NeuronInput:
    """Normalized input contract consumed by the core/neuron pipeline."""

    module_id: str
    signal: str
    value: Any
    input_id: str = field(default_factory=lambda: _make_id("nin"))
    input_model: str = DEFAULT_INPUT_MODEL
    source_event_id: str | None = None
    zone_id: str | None = None
    entity_id: str | None = None
    domain: str | None = None
    confidence: float = 1.0
    observed_at_ms: int = field(default_factory=_now_ms)
    context: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    neuron_targets: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.module_id:
            raise ValueError("module_id is required")
        if not self.signal:
            raise ValueError("signal is required")
        object.__setattr__(self, "domain", _infer_domain(self.entity_id, self.domain))
        object.__setattr__(self, "confidence", _coerce_confidence(self.confidence))
        object.__setattr__(self, "context", _copy_dict(self.context))
        object.__setattr__(self, "tags", _copy_list(self.tags))
        object.__setattr__(self, "neuron_targets", _copy_list(self.neuron_targets))
        object.__setattr__(self, "metadata", _copy_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_id": self.input_id,
            "input_model": self.input_model,
            "module_id": self.module_id,
            "source_event_id": self.source_event_id,
            "zone_id": self.zone_id,
            "entity_id": self.entity_id,
            "domain": self.domain,
            "signal": self.signal,
            "value": self.value,
            "confidence": self.confidence,
            "observed_at_ms": self.observed_at_ms,
            "context": dict(self.context),
            "tags": list(self.tags),
            "neuron_targets": list(self.neuron_targets),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NeuronInput":
        return cls(
            input_id=str(data.get("input_id") or _make_id("nin")),
            input_model=str(data.get("input_model") or DEFAULT_INPUT_MODEL),
            module_id=str(data["module_id"]),
            source_event_id=data.get("source_event_id"),
            zone_id=data.get("zone_id"),
            entity_id=data.get("entity_id"),
            domain=data.get("domain"),
            signal=str(data["signal"]),
            value=data.get("value"),
            confidence=float(data.get("confidence", 1.0)),
            observed_at_ms=int(data.get("observed_at_ms") or _now_ms()),
            context=_copy_dict(data.get("context")),
            tags=_copy_list(data.get("tags")),
            neuron_targets=_copy_list(data.get("neuron_targets")),
            metadata=_copy_dict(data.get("metadata")),
        )


@dataclass(frozen=True)
class ProposalIntent:
    """Suggestion-first outbound intent emitted by the core."""

    module_id: str
    action_type: str
    title: str
    summary: str
    proposal_id: str = field(default_factory=lambda: _make_id("proposal"))
    zone_id: str | None = None
    target: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    explanation: str = ""
    suggestion_mode: str = DEFAULT_SUGGESTION_MODE
    autonomy_mode: str = "learning"
    direct_execution_enabled: bool = False
    approval_required: bool = True
    explanation_required: bool = True
    requires_confirmation: bool = True
    output_adapter: str = "homeassistant"
    source_input_ids: list[str] = field(default_factory=list)
    source_event_ids: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at_ms: int = field(default_factory=_now_ms)

    def __post_init__(self) -> None:
        if not self.module_id:
            raise ValueError("module_id is required")
        if not self.action_type:
            raise ValueError("action_type is required")
        if not self.title:
            raise ValueError("title is required")
        if self.autonomy_mode not in VALID_AUTONOMY_MODES:
            raise ValueError(f"Unsupported autonomy_mode: {self.autonomy_mode}")
        object.__setattr__(self, "confidence", _coerce_confidence(self.confidence))
        object.__setattr__(self, "target", _copy_dict(self.target))
        object.__setattr__(self, "payload", _copy_dict(self.payload))
        object.__setattr__(self, "source_input_ids", _copy_list(self.source_input_ids))
        object.__setattr__(self, "source_event_ids", _copy_list(self.source_event_ids))
        object.__setattr__(self, "evidence", _copy_dict(self.evidence))
        object.__setattr__(self, "metadata", _copy_dict(self.metadata))

    def can_auto_execute(self) -> bool:
        """Return True only for explicitly autonomous, approval-free intents."""
        return (
            self.autonomy_mode == "autonomous"
            and self.direct_execution_enabled
            and not self.approval_required
            and not self.requires_confirmation
        )

    def to_action_intent(self, *, approved: bool = False) -> "ActionIntent":
        return ActionIntent(
            module_id=self.module_id,
            action_type=self.action_type,
            proposal_id=self.proposal_id,
            zone_id=self.zone_id,
            target=dict(self.target),
            payload=dict(self.payload),
            confidence=self.confidence,
            explanation=self.explanation,
            suggestion_mode=self.suggestion_mode,
            autonomy_mode=self.autonomy_mode,
            direct_execution_enabled=self.direct_execution_enabled,
            approval_required=self.approval_required,
            explanation_required=self.explanation_required,
            requires_confirmation=self.requires_confirmation,
            output_adapter=self.output_adapter,
            source_input_ids=list(self.source_input_ids),
            source_event_ids=list(self.source_event_ids),
            evidence=dict(self.evidence),
            metadata=dict(self.metadata),
            approved=approved,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "module_id": self.module_id,
            "zone_id": self.zone_id,
            "action_type": self.action_type,
            "title": self.title,
            "summary": self.summary,
            "target": dict(self.target),
            "payload": dict(self.payload),
            "confidence": self.confidence,
            "explanation": self.explanation,
            "suggestion_mode": self.suggestion_mode,
            "autonomy_mode": self.autonomy_mode,
            "direct_execution_enabled": self.direct_execution_enabled,
            "approval_required": self.approval_required,
            "explanation_required": self.explanation_required,
            "requires_confirmation": self.requires_confirmation,
            "output_adapter": self.output_adapter,
            "source_input_ids": list(self.source_input_ids),
            "source_event_ids": list(self.source_event_ids),
            "evidence": dict(self.evidence),
            "metadata": dict(self.metadata),
            "created_at_ms": self.created_at_ms,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProposalIntent":
        return cls(
            proposal_id=str(data.get("proposal_id") or _make_id("proposal")),
            module_id=str(data["module_id"]),
            action_type=str(data["action_type"]),
            title=str(data["title"]),
            summary=str(data.get("summary", "")),
            zone_id=data.get("zone_id"),
            target=_copy_dict(data.get("target")),
            payload=_copy_dict(data.get("payload")),
            confidence=float(data.get("confidence", 0.0)),
            explanation=str(data.get("explanation", "")),
            suggestion_mode=str(data.get("suggestion_mode") or DEFAULT_SUGGESTION_MODE),
            autonomy_mode=str(data.get("autonomy_mode") or "learning"),
            direct_execution_enabled=bool(data.get("direct_execution_enabled", False)),
            approval_required=bool(data.get("approval_required", True)),
            explanation_required=bool(data.get("explanation_required", True)),
            requires_confirmation=bool(data.get("requires_confirmation", True)),
            output_adapter=str(data.get("output_adapter") or "homeassistant"),
            source_input_ids=_copy_list(data.get("source_input_ids")),
            source_event_ids=_copy_list(data.get("source_event_ids")),
            evidence=_copy_dict(data.get("evidence")),
            metadata=_copy_dict(data.get("metadata")),
            created_at_ms=int(data.get("created_at_ms") or _now_ms()),
        )


@dataclass(frozen=True)
class ActionIntent:
    """Execution-capable intent derived from a proposal or direct core decision."""

    module_id: str
    action_type: str
    action_id: str = field(default_factory=lambda: _make_id("action"))
    proposal_id: str | None = None
    zone_id: str | None = None
    target: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    explanation: str = ""
    suggestion_mode: str = DEFAULT_SUGGESTION_MODE
    autonomy_mode: str = "learning"
    direct_execution_enabled: bool = False
    approval_required: bool = True
    explanation_required: bool = True
    requires_confirmation: bool = True
    output_adapter: str = "homeassistant"
    source_input_ids: list[str] = field(default_factory=list)
    source_event_ids: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    approved: bool = False
    created_at_ms: int = field(default_factory=_now_ms)

    def __post_init__(self) -> None:
        if not self.module_id:
            raise ValueError("module_id is required")
        if not self.action_type:
            raise ValueError("action_type is required")
        if self.autonomy_mode not in VALID_AUTONOMY_MODES:
            raise ValueError(f"Unsupported autonomy_mode: {self.autonomy_mode}")
        object.__setattr__(self, "confidence", _coerce_confidence(self.confidence))
        object.__setattr__(self, "target", _copy_dict(self.target))
        object.__setattr__(self, "payload", _copy_dict(self.payload))
        object.__setattr__(self, "source_input_ids", _copy_list(self.source_input_ids))
        object.__setattr__(self, "source_event_ids", _copy_list(self.source_event_ids))
        object.__setattr__(self, "evidence", _copy_dict(self.evidence))
        object.__setattr__(self, "metadata", _copy_dict(self.metadata))

    def can_execute(self) -> bool:
        """Respect suggest-first semantics unless approved or explicitly autonomous."""
        if self.autonomy_mode == "off":
            return False
        if self.requires_confirmation and not self.approved:
            return False
        if self.approval_required and not self.approved:
            return False
        if self.approved:
            return True
        return self.autonomy_mode == "autonomous" and self.direct_execution_enabled

    def to_module_command(self) -> "HabitatModuleCommand":
        return HabitatModuleCommand.from_action_intent(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "proposal_id": self.proposal_id,
            "module_id": self.module_id,
            "zone_id": self.zone_id,
            "action_type": self.action_type,
            "target": dict(self.target),
            "payload": dict(self.payload),
            "confidence": self.confidence,
            "explanation": self.explanation,
            "suggestion_mode": self.suggestion_mode,
            "autonomy_mode": self.autonomy_mode,
            "direct_execution_enabled": self.direct_execution_enabled,
            "approval_required": self.approval_required,
            "explanation_required": self.explanation_required,
            "requires_confirmation": self.requires_confirmation,
            "output_adapter": self.output_adapter,
            "source_input_ids": list(self.source_input_ids),
            "source_event_ids": list(self.source_event_ids),
            "evidence": dict(self.evidence),
            "metadata": dict(self.metadata),
            "approved": self.approved,
            "created_at_ms": self.created_at_ms,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ActionIntent":
        return cls(
            action_id=str(data.get("action_id") or _make_id("action")),
            proposal_id=data.get("proposal_id"),
            module_id=str(data["module_id"]),
            zone_id=data.get("zone_id"),
            action_type=str(data["action_type"]),
            target=_copy_dict(data.get("target")),
            payload=_copy_dict(data.get("payload")),
            confidence=float(data.get("confidence", 0.0)),
            explanation=str(data.get("explanation", "")),
            suggestion_mode=str(data.get("suggestion_mode") or DEFAULT_SUGGESTION_MODE),
            autonomy_mode=str(data.get("autonomy_mode") or "learning"),
            direct_execution_enabled=bool(data.get("direct_execution_enabled", False)),
            approval_required=bool(data.get("approval_required", True)),
            explanation_required=bool(data.get("explanation_required", True)),
            requires_confirmation=bool(data.get("requires_confirmation", True)),
            output_adapter=str(data.get("output_adapter") or "homeassistant"),
            source_input_ids=_copy_list(data.get("source_input_ids")),
            source_event_ids=_copy_list(data.get("source_event_ids")),
            evidence=_copy_dict(data.get("evidence")),
            metadata=_copy_dict(data.get("metadata")),
            approved=bool(data.get("approved", False)),
            created_at_ms=int(data.get("created_at_ms") or _now_ms()),
        )


@dataclass(frozen=True)
class HabitatModuleCommand:
    """Module-facing command emitted after proposal / action evaluation."""

    module_id: str
    command_name: str
    command_id: str = field(default_factory=lambda: _make_id("cmd"))
    zone_id: str | None = None
    proposal_id: str | None = None
    action_id: str | None = None
    target: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    command_mode: str = "suggest"
    explanation: str = ""
    approved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at_ms: int = field(default_factory=_now_ms)

    def __post_init__(self) -> None:
        if not self.module_id:
            raise ValueError("module_id is required")
        if not self.command_name:
            raise ValueError("command_name is required")
        if self.command_mode not in VALID_COMMAND_MODES:
            raise ValueError(f"Unsupported command_mode: {self.command_mode}")
        object.__setattr__(self, "target", _copy_dict(self.target))
        object.__setattr__(self, "payload", _copy_dict(self.payload))
        object.__setattr__(self, "metadata", _copy_dict(self.metadata))

    @classmethod
    def from_proposal_intent(cls, proposal: ProposalIntent) -> "HabitatModuleCommand":
        return cls(
            module_id=proposal.module_id,
            command_name=proposal.action_type,
            zone_id=proposal.zone_id,
            proposal_id=proposal.proposal_id,
            target=dict(proposal.target),
            payload=dict(proposal.payload),
            command_mode="suggest",
            explanation=proposal.explanation,
            approved=False,
            metadata={
                "title": proposal.title,
                "summary": proposal.summary,
                "confidence": proposal.confidence,
                "suggestion_mode": proposal.suggestion_mode,
                "autonomy_mode": proposal.autonomy_mode,
                "direct_execution_enabled": proposal.direct_execution_enabled,
                "approval_required": proposal.approval_required,
                "requires_confirmation": proposal.requires_confirmation,
                "output_adapter": proposal.output_adapter,
                "evidence": dict(proposal.evidence),
                **dict(proposal.metadata),
            },
        )

    @classmethod
    def from_action_intent(cls, action: ActionIntent) -> "HabitatModuleCommand":
        return cls(
            module_id=action.module_id,
            command_name=action.action_type,
            zone_id=action.zone_id,
            proposal_id=action.proposal_id,
            action_id=action.action_id,
            target=dict(action.target),
            payload=dict(action.payload),
            command_mode="execute" if action.can_execute() else "suggest",
            explanation=action.explanation,
            approved=action.approved,
            metadata={
                "confidence": action.confidence,
                "suggestion_mode": action.suggestion_mode,
                "autonomy_mode": action.autonomy_mode,
                "direct_execution_enabled": action.direct_execution_enabled,
                "approval_required": action.approval_required,
                "requires_confirmation": action.requires_confirmation,
                "output_adapter": action.output_adapter,
                "evidence": dict(action.evidence),
                **dict(action.metadata),
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "module_id": self.module_id,
            "command_name": self.command_name,
            "zone_id": self.zone_id,
            "proposal_id": self.proposal_id,
            "action_id": self.action_id,
            "target": dict(self.target),
            "payload": dict(self.payload),
            "command_mode": self.command_mode,
            "explanation": self.explanation,
            "approved": self.approved,
            "metadata": dict(self.metadata),
            "created_at_ms": self.created_at_ms,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HabitatModuleCommand":
        return cls(
            command_id=str(data.get("command_id") or _make_id("cmd")),
            module_id=str(data["module_id"]),
            command_name=str(data["command_name"]),
            zone_id=data.get("zone_id"),
            proposal_id=data.get("proposal_id"),
            action_id=data.get("action_id"),
            target=_copy_dict(data.get("target")),
            payload=_copy_dict(data.get("payload")),
            command_mode=str(data.get("command_mode") or "suggest"),
            explanation=str(data.get("explanation", "")),
            approved=bool(data.get("approved", False)),
            metadata=_copy_dict(data.get("metadata")),
            created_at_ms=int(data.get("created_at_ms") or _now_ms()),
        )


__all__ = [
    "DEFAULT_INPUT_MODEL",
    "DEFAULT_SUGGESTION_MODE",
    "VALID_AUTONOMY_MODES",
    "VALID_COMMAND_MODES",
    "HabitatModuleEvent",
    "NeuronInput",
    "ProposalIntent",
    "ActionIntent",
    "HabitatModuleCommand",
]
