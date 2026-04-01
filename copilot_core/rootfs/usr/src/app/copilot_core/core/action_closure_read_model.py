"""Action-closure summary read models for Slice 18.

Turns the canonical ActionClosure store into one stable summary/context surface for
APIs, dashboard consumers, and chat context assembly.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from copilot_core.action_closure import ActionClosureStore, get_action_closure_store
from copilot_core.core.dashboard_read_models import ReadModelMeta

_SUCCESS_STATES = {"executed", "completed", "succeeded", "success"}
_FAILURE_STATES = {"failed", "error", "blocked", "denied", "rejected", "cancelled"}
_OPEN_STATES = {"accepted", "feedback_received", "queued", "pending", "scheduled", "awaiting_execution"}


def _as_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _sort_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _compact_recent_closure(closure: Mapping[str, Any]) -> dict[str, Any]:
    latest_feedback = closure.get("latest_feedback") or {}
    execution = closure.get("execution") or {}
    return {
        "closure_id": closure.get("closure_id"),
        "source": closure.get("source"),
        "state": closure.get("state"),
        "proposal_id": closure.get("proposal_id"),
        "action_id": closure.get("action_id"),
        "zone_id": closure.get("zone_id"),
        "module_id": closure.get("module_id"),
        "subject_type": closure.get("subject_type"),
        "subject_id": closure.get("subject_id"),
        "feedback": latest_feedback.get("feedback"),
        "feedback_comment": latest_feedback.get("comment"),
        "execution_outcome": execution.get("outcome"),
        "runtime_source": execution.get("runtime_source"),
        "updated_at": closure.get("updated_at"),
    }


def _describe_recent_closure(closure: Mapping[str, Any]) -> str | None:
    zone_id = _as_text(closure.get("zone_id"))
    module_id = _as_text(closure.get("module_id"))
    action_id = _as_text(closure.get("action_id"))
    state = _as_text(closure.get("state")) or "unknown"

    target = zone_id or module_id or action_id or _as_text(closure.get("closure_id"))
    if not target:
        return None

    if zone_id and module_id:
        target = f"{zone_id}/{module_id}"

    if state in _SUCCESS_STATES:
        return f"Letzte Ausfuehrung erfolgreich: {target}"
    if state in _FAILURE_STATES:
        return f"Letzte Ausfuehrung problematisch: {target} ({state})"
    return f"Letzte Aktion offen: {target} ({state})"


@dataclass
class ActionClosureSummaryReadModel:
    meta: ReadModelMeta
    total_closures: int = 0
    open_count: int = 0
    terminal_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    feedback_count: int = 0
    success_rate: float = 0.0
    states: dict[str, int] = field(default_factory=dict)
    outcomes: dict[str, int] = field(default_factory=dict)
    feedback_signals: dict[str, int] = field(default_factory=dict)
    sources: dict[str, int] = field(default_factory=dict)
    zones: dict[str, int] = field(default_factory=dict)
    modules: dict[str, int] = field(default_factory=dict)
    recent_closures: list[dict[str, Any]] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ActionClosureSummaryV1",
            **self.meta.to_dict(),
            "total_closures": self.total_closures,
            "open_count": self.open_count,
            "terminal_count": self.terminal_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "feedback_count": self.feedback_count,
            "success_rate": self.success_rate,
            "states": dict(self.states),
            "outcomes": dict(self.outcomes),
            "feedback_signals": dict(self.feedback_signals),
            "sources": dict(self.sources),
            "zones": dict(self.zones),
            "modules": dict(self.modules),
            "recent_closures": [dict(item) for item in self.recent_closures],
            "highlights": list(self.highlights),
        }

    @classmethod
    def build(
        cls,
        store: ActionClosureStore | None = None,
        *,
        closures: Sequence[Mapping[str, Any]] | None = None,
        source: str | None = None,
        zone_id: str | None = None,
        module_id: str | None = None,
        state: str | None = None,
        action_id: str | None = None,
        proposal_id: str | None = None,
        recent_limit: int = 5,
    ) -> "ActionClosureSummaryReadModel":
        store = store or get_action_closure_store()
        if closures is None:
            closures = store.list(
                source=source,
                zone_id=zone_id,
                module_id=module_id,
                state=state,
                action_id=action_id,
                proposal_id=proposal_id,
            )

        closures = list(closures)
        meta = ReadModelMeta(source="action_closure")
        state_counter: Counter[str] = Counter()
        outcome_counter: Counter[str] = Counter()
        feedback_counter: Counter[str] = Counter()
        source_counter: Counter[str] = Counter()
        zone_counter: Counter[str] = Counter()
        module_counter: Counter[str] = Counter()

        success_count = 0
        failure_count = 0
        feedback_count = 0
        open_count = 0
        terminal_count = 0

        for closure in closures:
            closure_state = _as_text(closure.get("state")) or "unknown"
            state_counter[closure_state] += 1

            closure_source = _as_text(closure.get("source"))
            if closure_source:
                source_counter[closure_source] += 1

            closure_zone = _as_text(closure.get("zone_id"))
            if closure_zone:
                zone_counter[closure_zone] += 1

            closure_module = _as_text(closure.get("module_id"))
            if closure_module:
                module_counter[closure_module] += 1

            execution = closure.get("execution") or {}
            outcome = _as_text(execution.get("outcome"))
            if outcome:
                outcome_counter[outcome] += 1

            latest_feedback = closure.get("latest_feedback") or {}
            feedback = _as_text(latest_feedback.get("feedback"))
            if feedback:
                feedback_counter[feedback] += 1
                feedback_count += 1

            if closure_state in _SUCCESS_STATES:
                success_count += 1
                terminal_count += 1
            elif closure_state in _FAILURE_STATES:
                failure_count += 1
                terminal_count += 1
            elif outcome in _SUCCESS_STATES:
                success_count += 1
                terminal_count += 1
            elif outcome in _FAILURE_STATES:
                failure_count += 1
                terminal_count += 1
            elif closure_state in _OPEN_STATES or outcome is None:
                open_count += 1
            else:
                terminal_count += 1

        success_rate = round(success_count / terminal_count, 3) if terminal_count else 0.0
        recent = [_compact_recent_closure(item) for item in closures[: max(1, recent_limit)]] if closures else []

        highlights: list[str] = []
        if closures:
            highlights.append(
                f"{len(closures)} Closures, {open_count} offen, {success_count} erfolgreich, {failure_count} problematisch"
            )
            if feedback_counter:
                top_feedback, top_feedback_count = feedback_counter.most_common(1)[0]
                highlights.append(f"Staerkstes Feedback: {top_feedback} ({top_feedback_count})")
            recent_line = _describe_recent_closure(closures[0])
            if recent_line:
                highlights.append(recent_line)

        return cls(
            meta=meta,
            total_closures=len(closures),
            open_count=open_count,
            terminal_count=terminal_count,
            success_count=success_count,
            failure_count=failure_count,
            feedback_count=feedback_count,
            success_rate=success_rate,
            states=_sort_counter(state_counter),
            outcomes=_sort_counter(outcome_counter),
            feedback_signals=_sort_counter(feedback_counter),
            sources=_sort_counter(source_counter),
            zones=_sort_counter(zone_counter),
            modules=_sort_counter(module_counter),
            recent_closures=recent,
            highlights=highlights,
        )


@dataclass
class ActionClosureContextBlock:
    meta: ReadModelMeta
    summary: dict[str, Any] = field(default_factory=dict)
    recent_closures: list[dict[str, Any]] = field(default_factory=list)
    context_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ActionClosureContextBlockV1",
            **self.meta.to_dict(),
            "summary": dict(self.summary),
            "recent_closures": [dict(item) for item in self.recent_closures],
            "context_lines": list(self.context_lines),
        }


def build_action_closure_summary_read_model(
    store: ActionClosureStore | None = None,
    *,
    source: str | None = None,
    zone_id: str | None = None,
    module_id: str | None = None,
    state: str | None = None,
    action_id: str | None = None,
    proposal_id: str | None = None,
    recent_limit: int = 5,
) -> ActionClosureSummaryReadModel:
    return ActionClosureSummaryReadModel.build(
        store,
        source=source,
        zone_id=zone_id,
        module_id=module_id,
        state=state,
        action_id=action_id,
        proposal_id=proposal_id,
        recent_limit=recent_limit,
    )


def build_action_closure_context_block(
    store: ActionClosureStore | None = None,
    *,
    source: str | None = None,
    zone_id: str | None = None,
    module_id: str | None = None,
    state: str | None = None,
    action_id: str | None = None,
    proposal_id: str | None = None,
    recent_limit: int = 3,
) -> ActionClosureContextBlock:
    summary = build_action_closure_summary_read_model(
        store,
        source=source,
        zone_id=zone_id,
        module_id=module_id,
        state=state,
        action_id=action_id,
        proposal_id=proposal_id,
        recent_limit=recent_limit,
    )
    payload = summary.to_dict()

    context_lines: list[str] = []
    if summary.total_closures:
        context_lines.append(
            "Aktionsabschluesse: "
            f"{summary.total_closures} gesamt, {summary.open_count} offen, "
            f"{summary.success_count} erfolgreich, {summary.failure_count} problematisch"
        )
        if summary.feedback_signals:
            feedback_label, feedback_count = next(iter(summary.feedback_signals.items()))
            context_lines.append(f"Rueckmeldungsbild: {feedback_label} ({feedback_count})")
        recent_line = _describe_recent_closure(summary.recent_closures[0]) if summary.recent_closures else None
        if recent_line:
            context_lines.append(recent_line)

    return ActionClosureContextBlock(
        meta=ReadModelMeta(source="action_closure.context"),
        summary={
            "total_closures": payload.get("total_closures", 0),
            "open_count": payload.get("open_count", 0),
            "success_count": payload.get("success_count", 0),
            "failure_count": payload.get("failure_count", 0),
            "feedback_count": payload.get("feedback_count", 0),
            "success_rate": payload.get("success_rate", 0.0),
            "states": payload.get("states", {}),
            "outcomes": payload.get("outcomes", {}),
            "feedback_signals": payload.get("feedback_signals", {}),
            "sources": payload.get("sources", {}),
        },
        recent_closures=payload.get("recent_closures", []),
        context_lines=context_lines,
    )


__all__ = [
    "ActionClosureSummaryReadModel",
    "ActionClosureContextBlock",
    "build_action_closure_summary_read_model",
    "build_action_closure_context_block",
]
