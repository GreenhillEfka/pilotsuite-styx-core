"""Canonical action feedback / execution closure store for Slice 17.

Unifies the post-acceptance trail for proposal → action → runtime flows so
Voice, Predictive, Habitus and Multi-Zone can attach feedback and execution
outcomes to the same canonical contract surface.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy_mapping(value: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return dict(value or {})


def _copy_list(value: list[Any] | tuple[Any, ...] | None = None) -> list[Any]:
    return list(value or [])


def _subset_match(actual: Mapping[str, Any] | None, expected: Mapping[str, Any] | None) -> bool:
    if not expected:
        return True
    actual = actual or {}
    for key, value in expected.items():
        current = actual.get(key)
        if isinstance(value, Mapping):
            if not isinstance(current, Mapping) or not _subset_match(current, value):
                return False
            continue
        if current != value:
            return False
    return True


def _feedback_signal(value: Any) -> float:
    text = str(value or "").strip().lower()
    if not text:
        return 0.0
    positive = {
        "accepted",
        "confirmed",
        "good",
        "great",
        "helpful",
        "success",
        "thumbs_up",
        "useful",
        "worked",
        "worked_well",
    }
    negative = {
        "bad",
        "cancelled",
        "failed",
        "incorrect",
        "not_now",
        "problem",
        "rejected",
        "snoozed",
        "thumbs_down",
        "wrong",
    }
    if text in positive:
        return 1.0
    if text in negative:
        return -1.0
    if any(token in text for token in ("worked", "good", "helpful", "success")):
        return 1.0
    if any(token in text for token in ("fail", "wrong", "reject", "not_now", "cancel")):
        return -1.0
    return 0.0


def _execution_signal(value: Any) -> float:
    text = str(value or "").strip().lower()
    if not text:
        return 0.0
    positive = {"applied", "completed", "executed", "success", "succeeded"}
    negative = {"blocked", "cancelled", "error", "failed", "problematic", "timed_out"}
    if text in positive:
        return 1.5
    if text in negative:
        return -1.5
    if any(token in text for token in ("execut", "success", "complete", "appl")):
        return 1.5
    if any(token in text for token in ("fail", "block", "error", "cancel", "timeout", "problem")):
        return -1.5
    return 0.0


def _action_ref(action_intent: Mapping[str, Any] | None = None, action_id: str | None = None) -> str | None:
    if action_id:
        return str(action_id).strip() or None
    if isinstance(action_intent, Mapping):
        for key in ("action_intent_id", "action_id"):
            value = action_intent.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _closure_id(source: str, proposal_id: str | None, action_ref: str | None, zone_id: str | None, module_id: str | None) -> str:
    seed = "|".join([
        str(source or "unknown"),
        str(proposal_id or "unknown"),
        str(action_ref or "unknown"),
        str(zone_id or "unknown"),
        str(module_id or "unknown"),
    ])
    return f"closure:{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:12]}"


@dataclass
class ActionClosureRecord:
    closure_id: str
    source: str
    proposal_id: str | None = None
    action_id: str | None = None
    zone_id: str | None = None
    module_id: str | None = None
    state: str = "accepted"
    accepted_at: str | None = None
    service_call: dict[str, Any] = field(default_factory=dict)
    policy_gate: dict[str, Any] = field(default_factory=dict)
    proposal_intent: dict[str, Any] | None = None
    action_intent: dict[str, Any] | None = None
    subject_type: str | None = None
    subject_id: str | None = None
    latest_feedback: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    feedback_history: list[dict[str, Any]] = field(default_factory=list)
    event_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ActionClosureV1",
            "closure_id": self.closure_id,
            "source": self.source,
            "proposal_id": self.proposal_id,
            "action_id": self.action_id,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "state": self.state,
            "accepted_at": self.accepted_at,
            "service_call": dict(self.service_call),
            "policy_gate": dict(self.policy_gate),
            "proposal_intent": _copy_mapping(self.proposal_intent),
            "action_intent": _copy_mapping(self.action_intent),
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "latest_feedback": _copy_mapping(self.latest_feedback),
            "execution": _copy_mapping(self.execution),
            "feedback_history": [dict(item) for item in self.feedback_history],
            "event_history": [dict(item) for item in self.event_history],
            "metadata": dict(self.metadata),
            "updated_at": self.updated_at,
        }


class ActionClosureStore:
    def __init__(self) -> None:
        self._records: dict[str, ActionClosureRecord] = {}

    def clear(self) -> None:
        self._records.clear()

    def upsert(
        self,
        *,
        source: str,
        proposal_id: str | None = None,
        action_id: str | None = None,
        action_intent: Mapping[str, Any] | None = None,
        proposal_intent: Mapping[str, Any] | None = None,
        zone_id: str | None = None,
        module_id: str | None = None,
        service_call: Mapping[str, Any] | None = None,
        policy_gate: Mapping[str, Any] | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        accepted_at: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        action_ref = _action_ref(action_intent, action_id)
        closure_id = _closure_id(source, proposal_id, action_ref, zone_id, module_id)
        record = self._records.get(closure_id)
        if record is None:
            record = ActionClosureRecord(
                closure_id=closure_id,
                source=str(source or "unknown"),
                proposal_id=proposal_id,
                action_id=action_ref,
                zone_id=zone_id,
                module_id=module_id,
                accepted_at=accepted_at,
                service_call=_copy_mapping(service_call),
                policy_gate=_copy_mapping(policy_gate),
                proposal_intent=_copy_mapping(proposal_intent),
                action_intent=_copy_mapping(action_intent),
                subject_type=subject_type,
                subject_id=subject_id,
                metadata=_copy_mapping(metadata),
            )
            record.event_history.append({
                "event_type": "accepted",
                "timestamp": accepted_at or _utcnow(),
                "source": record.source,
            })
            self._records[closure_id] = record
        else:
            if proposal_id and not record.proposal_id:
                record.proposal_id = proposal_id
            if action_ref and not record.action_id:
                record.action_id = action_ref
            if zone_id and not record.zone_id:
                record.zone_id = zone_id
            if module_id and not record.module_id:
                record.module_id = module_id
            if accepted_at and not record.accepted_at:
                record.accepted_at = accepted_at
            if service_call:
                record.service_call = _copy_mapping(service_call)
            if policy_gate:
                record.policy_gate = _copy_mapping(policy_gate)
            if proposal_intent:
                record.proposal_intent = _copy_mapping(proposal_intent)
            if action_intent:
                record.action_intent = _copy_mapping(action_intent)
            if subject_type:
                record.subject_type = subject_type
            if subject_id:
                record.subject_id = subject_id
            if metadata:
                record.metadata.update(_copy_mapping(metadata))
        record.updated_at = _utcnow()
        return record.to_dict()

    def get(self, closure_id: str) -> dict[str, Any] | None:
        record = self._records.get(str(closure_id or "").strip())
        return record.to_dict() if record else None

    def list(
        self,
        *,
        source: str | None = None,
        zone_id: str | None = None,
        module_id: str | None = None,
        state: str | None = None,
        action_id: str | None = None,
        proposal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        items = [record for record in self._records.values()]
        if source:
            items = [record for record in items if record.source == source]
        if zone_id:
            items = [record for record in items if record.zone_id == zone_id]
        if module_id:
            items = [record for record in items if record.module_id == module_id]
        if state:
            items = [record for record in items if record.state == state]
        if action_id:
            items = [record for record in items if record.action_id == action_id]
        if proposal_id:
            items = [record for record in items if record.proposal_id == proposal_id]
        items.sort(key=lambda record: (record.accepted_at or "", record.closure_id), reverse=True)
        return [record.to_dict() for record in items]

    def get_learning_summary(
        self,
        *,
        source: str | None = None,
        zone_id: str | None = None,
        module_id: str | None = None,
        state: str | None = None,
        action_id: str | None = None,
        proposal_id: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        service_call: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        items = [record for record in self._records.values()]
        if source:
            items = [record for record in items if record.source == source]
        if zone_id:
            items = [record for record in items if record.zone_id == zone_id]
        if module_id:
            items = [record for record in items if record.module_id == module_id]
        if state:
            items = [record for record in items if record.state == state]
        if action_id:
            items = [record for record in items if record.action_id == action_id]
        if proposal_id:
            items = [record for record in items if record.proposal_id == proposal_id]
        if subject_type:
            items = [record for record in items if record.subject_type == subject_type]
        if subject_id:
            items = [record for record in items if record.subject_id == subject_id]
        if metadata:
            items = [record for record in items if _subset_match(record.metadata, metadata)]
        if service_call:
            items = [record for record in items if _subset_match(record.service_call, service_call)]

        accepted = len(items)
        feedback_positive = 0
        feedback_negative = 0
        executed = 0
        problematic = 0
        signal_total = 0.0

        for record in items:
            signal_total += 0.15
            for feedback in record.feedback_history:
                score = _feedback_signal(feedback.get("feedback"))
                if score > 0:
                    feedback_positive += 1
                elif score < 0:
                    feedback_negative += 1
                signal_total += score

            if record.execution:
                score = _execution_signal(record.execution.get("outcome"))
                if score > 0:
                    executed += 1
                elif score < 0:
                    problematic += 1
                signal_total += score

        normalized = 0.0
        if items:
            normalized = max(-1.0, min(1.0, signal_total / max(len(items), 1)))

        priority_bias = max(-3.0, min(3.0, round(normalized * 3.0, 3)))
        return {
            "accepted": accepted,
            "feedback_positive": feedback_positive,
            "feedback_negative": feedback_negative,
            "executed": executed,
            "problematic": problematic,
            "score": round(normalized, 3),
            "priority_bias": priority_bias,
        }

    def record_feedback(
        self,
        closure_id: str,
        *,
        feedback: str,
        comment: str | None = None,
        actor: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = self._records[str(closure_id or "").strip()]
        event = {
            "event_type": "feedback",
            "timestamp": _utcnow(),
            "feedback": str(feedback or "").strip() or "unspecified",
            "comment": str(comment or "").strip() or None,
            "actor": str(actor or "user").strip() or "user",
            "metadata": _copy_mapping(metadata),
        }
        record.latest_feedback = dict(event)
        record.feedback_history.append(dict(event))
        record.event_history.append(dict(event))
        record.state = "feedback_received"
        record.updated_at = event["timestamp"]
        return record.to_dict()

    def record_execution(
        self,
        closure_id: str,
        *,
        outcome: str,
        runtime_source: str | None = None,
        result: Mapping[str, Any] | None = None,
        error: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        executed_at: str | None = None,
    ) -> dict[str, Any]:
        record = self._records[str(closure_id or "").strip()]
        timestamp = executed_at or _utcnow()
        execution = {
            "outcome": str(outcome or "unknown").strip() or "unknown",
            "runtime_source": str(runtime_source or "runtime.unknown").strip() or "runtime.unknown",
            "result": _copy_mapping(result),
            "error": str(error or "").strip() or None,
            "executed_at": timestamp,
            "metadata": _copy_mapping(metadata),
        }
        record.execution = execution
        record.event_history.append({"event_type": "execution", **execution})
        record.state = execution["outcome"]
        record.updated_at = timestamp
        return record.to_dict()


_STORE = ActionClosureStore()


def get_action_closure_store() -> ActionClosureStore:
    return _STORE


__all__ = ["ActionClosureStore", "get_action_closure_store"]
