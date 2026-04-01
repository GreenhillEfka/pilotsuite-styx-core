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


def _latest_change_at(closures: Sequence[Mapping[str, Any]]) -> str | None:
    for closure in closures:
        updated_at = _as_text(closure.get("updated_at"))
        if updated_at:
            return updated_at
    return None


def _build_delta_payload(
    delta_closures: Sequence[Mapping[str, Any]],
    *,
    since_revision: int | None,
    current_revision: int,
    recent_limit: int,
) -> dict[str, Any]:
    return {
        "contract": "ActionClosureDeltaV1",
        "since_revision": since_revision,
        "current_revision": current_revision,
        "changed": bool(delta_closures),
        "changed_count": len(delta_closures),
        "latest_change_at": _latest_change_at(delta_closures),
        "recent_closures": [
            _compact_recent_closure(item) for item in list(delta_closures)[: max(1, recent_limit)]
        ],
    }


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
    revision: int = 0
    latest_change_at: str | None = None
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
    delta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ActionClosureSummaryV1",
            **self.meta.to_dict(),
            "revision": self.revision,
            "latest_change_at": self.latest_change_at,
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
            "delta": dict(self.delta),
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
        since_revision: int | None = None,
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
        latest_change_at = _latest_change_at(closures)
        meta = ReadModelMeta(source="action_closure", freshness=latest_change_at or ReadModelMeta().freshness)
        current_revision = store.get_current_revision() if hasattr(store, "get_current_revision") else 0
        delta_closures = store.list(
            source=source,
            zone_id=zone_id,
            module_id=module_id,
            state=state,
            action_id=action_id,
            proposal_id=proposal_id,
            since_revision=since_revision,
        )
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
            revision=current_revision,
            latest_change_at=latest_change_at,
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
            delta=_build_delta_payload(
                delta_closures,
                since_revision=since_revision,
                current_revision=current_revision,
                recent_limit=recent_limit,
            ),
        )


@dataclass
class ActionClosureContextBlock:
    meta: ReadModelMeta
    revision: int = 0
    latest_change_at: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)
    recent_closures: list[dict[str, Any]] = field(default_factory=list)
    context_lines: list[str] = field(default_factory=list)
    delta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ActionClosureContextBlockV1",
            **self.meta.to_dict(),
            "revision": self.revision,
            "latest_change_at": self.latest_change_at,
            "summary": dict(self.summary),
            "recent_closures": [dict(item) for item in self.recent_closures],
            "context_lines": list(self.context_lines),
            "delta": dict(self.delta),
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
    since_revision: int | None = None,
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
        since_revision=since_revision,
    )


def resolve_zone_name(zone_id: str | None) -> str | None:
    """Resolve a zone_id (e.g. 'zone:living') to a human-readable zone name."""
    if not zone_id:
        return None
    zone_id = str(zone_id).strip()
    if zone_id.startswith("zone:"):
        slug = zone_id[len("zone:") :]
    else:
        slug = zone_id
    slug = slug.strip()
    if not slug:
        return None
    # Try to map known zone slugs to friendly names
    _ZONE_SLUG_MAP = {
        "living": "Wohnzimmer",
        "living_h": "Wohnzimmer",
        "schlafzimmer": "Schlafzimmer",
        "schlafzimmer_h": "Schlafzimmer",
        "kueche": "Kueche",
        "kueche_h": "Kueche",
        "kitchen": "Kueche",
        "buero": "Buero",
        "buero_h": "Buero",
        "office": "Buero",
        "bad": "Bad",
        "bathroom": "Bad",
        "flur": "Flur",
        "hallway": "Flur",
        "garten": "Garten",
        "garden": "Garten",
        "terrasse": "Terasse",
        "terrace": "Terasse",
        "balkon": "Balkon",
        "balcony": "Balkon",
    }
    return _ZONE_SLUG_MAP.get(slug.lower(), slug.replace("_", " ").title())


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
    zone_name: str | None = None,
    since_revision: int | None = None,
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
        since_revision=since_revision,
    )
    payload = summary.to_dict()

    # Resolve human-readable zone name from zone_id when not provided
    resolved_zone_name = zone_name or resolve_zone_name(zone_id)

    context_lines: list[str] = []
    if summary.total_closures:
        if resolved_zone_name:
            context_lines.append(f"Zone: {resolved_zone_name}")
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
    elif since_revision is not None and resolved_zone_name:
        context_lines.append(f"Zone: {resolved_zone_name}")

    delta_payload = payload.get("delta", {})
    if since_revision is not None:
        if delta_payload.get("changed"):
            context_lines.append(
                f"Closure-Deltas seit Revision {since_revision}: {delta_payload.get('changed_count', 0)}"
            )
        else:
            context_lines.append(f"Keine Closure-Aenderungen seit Revision {since_revision}")

    return ActionClosureContextBlock(
        meta=ReadModelMeta(
            source="action_closure.context",
            freshness=payload.get("latest_change_at") or payload.get("freshness") or ReadModelMeta().freshness,
        ),
        revision=payload.get("revision", 0),
        latest_change_at=payload.get("latest_change_at"),
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
        delta=delta_payload,
    )


__all__ = [
    "ActionClosureSummaryReadModel",
    "ActionClosureContextBlock",
    "build_action_closure_summary_read_model",
    "build_action_closure_context_block",
    "resolve_zone_name",
]
