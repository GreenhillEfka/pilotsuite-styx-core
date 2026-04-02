"""Canonical proposal lifecycle status read models for Slice 30.

Materializes one truth-backed per-proposal lifecycle surface from the existing
proposal/action/closure/follow-up settlement data, without introducing a
separate timeline table.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from copilot_core.action_closure import ActionClosureStore, get_action_closure_store
from copilot_core.core.dashboard_read_models import ReadModelMeta

_SUCCESS_STATES = {"executed", "completed", "succeeded", "success"}
_FAILURE_STATES = {"failed", "error", "blocked", "denied", "rejected", "cancelled"}
_ACCEPTED_STATES = {
    "accepted",
    "feedback_received",
    "queued",
    "pending",
    "scheduled",
    "awaiting_execution",
}
_ENGINE_SUGGESTED_STATES = {"proposed"}
_ENGINE_ACCEPTED_STATES = {"ready_to_execute", "ready", "pending"}
_ENGINE_EXECUTED_STATES = {"executed"}
_ENGINE_FAILED_STATES = {"cancelled", "failed", "error", "rejected"}


def _as_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _sort_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _latest_change_at(items: Sequence[Mapping[str, Any]]) -> str | None:
    for item in items:
        latest = _as_text(item.get("latest_change_at")) or _as_text(item.get("updated_at"))
        if latest:
            return latest
    return None


def _compact_recent_status(item: Mapping[str, Any]) -> dict[str, Any]:
    worker = item.get("worker") or {}
    return {
        "proposal_id": item.get("proposal_id"),
        "lifecycle_status": item.get("lifecycle_status"),
        "revision": item.get("revision", 0),
        "source": item.get("source"),
        "zone_id": item.get("zone_id"),
        "module_id": item.get("module_id"),
        "action_id": item.get("action_id"),
        "closure_id": item.get("closure_id"),
        "latest_change_at": item.get("latest_change_at"),
        "closure_state": item.get("closure_state"),
        "settlement_state": worker.get("settlement_state"),
        "receipt_state": worker.get("receipt_state"),
        "claim_state": worker.get("claim_state"),
    }


def _describe_recent_status(item: Mapping[str, Any]) -> str | None:
    proposal_id = _as_text(item.get("proposal_id"))
    lifecycle_status = _as_text(item.get("lifecycle_status")) or "unknown"
    zone_id = _as_text(item.get("zone_id"))
    module_id = _as_text(item.get("module_id"))
    target = zone_id or module_id or proposal_id
    if not target:
        return None
    return f"Letzter Proposal-Status: {target} ({lifecycle_status})"


@dataclass
class ProposalLifecycleStatus:
    meta: ReadModelMeta
    proposal_id: str
    lifecycle_status: str
    revision: int = 0
    latest_change_at: str | None = None
    source: str | None = None
    zone_id: str | None = None
    module_id: str | None = None
    action_id: str | None = None
    action_intent_id: str | None = None
    closure_id: str | None = None
    closure_state: str | None = None
    proposal_state: str | None = None
    accepted_at: str | None = None
    executed_at: str | None = None
    title: str | None = None
    summary: str | None = None
    confidence: float | None = None
    worker: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ProposalLifecycleStatusV1",
            **self.meta.to_dict(),
            "proposal_id": self.proposal_id,
            "lifecycle_status": self.lifecycle_status,
            "revision": self.revision,
            "latest_change_at": self.latest_change_at,
            "source": self.source,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "action_id": self.action_id,
            "action_intent_id": self.action_intent_id,
            "closure_id": self.closure_id,
            "closure_state": self.closure_state,
            "proposal_state": self.proposal_state,
            "accepted_at": self.accepted_at,
            "executed_at": self.executed_at,
            "title": self.title,
            "summary": self.summary,
            "confidence": self.confidence,
            "worker": dict(self.worker),
        }


@dataclass
class ProposalLifecycleStatusSummaryReadModel:
    meta: ReadModelMeta
    revision: int = 0
    latest_change_at: str | None = None
    total_proposals: int = 0
    lifecycle_statuses: dict[str, int] = field(default_factory=dict)
    sources: dict[str, int] = field(default_factory=dict)
    zones: dict[str, int] = field(default_factory=dict)
    modules: dict[str, int] = field(default_factory=dict)
    recent_statuses: list[dict[str, Any]] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    delta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ProposalLifecycleStatusSummaryV1",
            **self.meta.to_dict(),
            "revision": self.revision,
            "latest_change_at": self.latest_change_at,
            "total_proposals": self.total_proposals,
            "lifecycle_statuses": dict(self.lifecycle_statuses),
            "sources": dict(self.sources),
            "zones": dict(self.zones),
            "modules": dict(self.modules),
            "recent_statuses": [dict(item) for item in self.recent_statuses],
            "highlights": list(self.highlights),
            "delta": dict(self.delta),
        }


def _build_delta_payload(
    delta_items: Sequence[Mapping[str, Any]],
    *,
    since_revision: int | None,
    current_revision: int,
    recent_limit: int,
) -> dict[str, Any]:
    return {
        "contract": "ProposalLifecycleStatusDeltaV1",
        "since_revision": since_revision,
        "current_revision": current_revision,
        "changed": bool(delta_items),
        "changed_count": len(delta_items),
        "latest_change_at": _latest_change_at(delta_items),
        "recent_statuses": [
            _compact_recent_status(item) for item in list(delta_items)[: max(1, recent_limit)]
        ],
    }


def _engine_zone_id(proposal: Mapping[str, Any]) -> str | None:
    for key in ("zone_id",):
        value = _as_text(proposal.get(key))
        if value:
            return value
    config = proposal.get("action_config") if isinstance(proposal.get("action_config"), Mapping) else {}
    params = proposal.get("params") if isinstance(proposal.get("params"), Mapping) else {}
    for container in (config, params):
        value = _as_text(container.get("zone_id"))
        if value:
            return value
    return None


def _engine_module_id(proposal: Mapping[str, Any]) -> str | None:
    for key in ("module_id", "domain", "action_type"):
        value = _as_text(proposal.get(key))
        if value:
            return value
    config = proposal.get("action_config") if isinstance(proposal.get("action_config"), Mapping) else {}
    params = proposal.get("params") if isinstance(proposal.get("params"), Mapping) else {}
    for container in (config, params):
        for key in ("module_id", "domain", "service"):
            value = _as_text(container.get(key))
            if value:
                return value
    return None


def _engine_lifecycle_status(proposal: Mapping[str, Any]) -> str:
    state = _as_text(proposal.get("status")) or "proposed"
    normalized = state.lower()
    if normalized in _ENGINE_EXECUTED_STATES:
        return "executed"
    if normalized in _ENGINE_FAILED_STATES:
        return "failed"
    if normalized in _ENGINE_ACCEPTED_STATES:
        return "accepted"
    if normalized in _ENGINE_SUGGESTED_STATES:
        return "suggested"
    return "suggested"


def _worker_truth_for_closure(closure_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, int]:
    try:
        from copilot_core.api.v1.notifications import get_action_closure_follow_up_dispatch_store
    except Exception:
        return None, None, 0

    store = get_action_closure_follow_up_dispatch_store()
    latest_claim = None
    latest_receipt = None

    try:
        claims = [item for item in store.list_claims() if item.get("closure_id") == closure_id]
        if claims:
            latest_claim = max(claims, key=lambda item: int(item.get("claim_revision") or 0))
    except Exception:
        latest_claim = None

    try:
        receipts = [item for item in store.list_receipts() if item.get("closure_id") == closure_id]
        if receipts:
            latest_receipt = max(receipts, key=lambda item: int(item.get("receipt_revision") or 0))
    except Exception:
        latest_receipt = None

    revision = max(
        int((latest_claim or {}).get("claim_revision") or 0),
        int((latest_receipt or {}).get("receipt_revision") or 0),
    )
    return latest_claim, latest_receipt, revision


def _status_from_closure(closure: Mapping[str, Any]) -> dict[str, Any] | None:
    proposal_id = _as_text(closure.get("proposal_id"))
    if not proposal_id:
        return None

    latest_claim, latest_receipt, worker_revision = _worker_truth_for_closure(str(closure.get("closure_id") or ""))
    settlement = (latest_claim or {}).get("settlement") or {}
    claim_state = _as_text((latest_claim or {}).get("claim_state"))
    settlement_state = _as_text(settlement.get("state"))
    if settlement_state is None and claim_state in {"settled", "released", "abandoned"}:
        settlement_state = claim_state
    receipt_state = _as_text((latest_receipt or {}).get("receipt_state"))

    closure_state = (_as_text(closure.get("state")) or "unknown").lower()
    execution = closure.get("execution") if isinstance(closure.get("execution"), Mapping) else {}
    execution_outcome = (_as_text(execution.get("outcome")) or "").lower()
    proposal_intent = closure.get("proposal_intent") if isinstance(closure.get("proposal_intent"), Mapping) else {}
    action_intent = closure.get("action_intent") if isinstance(closure.get("action_intent"), Mapping) else {}

    worker_engaged = latest_claim is not None or latest_receipt is not None
    if settlement_state == "settled":
        lifecycle_status = "settled"
    elif closure_state in _SUCCESS_STATES or execution_outcome in _SUCCESS_STATES:
        lifecycle_status = "executed"
    elif worker_engaged:
        lifecycle_status = "follow_up_open"
    elif closure_state in _FAILURE_STATES or execution_outcome in _FAILURE_STATES:
        lifecycle_status = "failed"
    else:
        lifecycle_status = "accepted"

    revision = max(int(closure.get("revision") or 0), worker_revision)
    latest_change_at = (
        _as_text(settlement.get("at"))
        or _as_text((latest_claim or {}).get("updated_at"))
        or _as_text((latest_receipt or {}).get("updated_at"))
        or _as_text(closure.get("updated_at"))
    )

    return {
        "contract": "ProposalLifecycleStatusV1",
        "proposal_id": proposal_id,
        "lifecycle_status": lifecycle_status,
        "revision": revision,
        "latest_change_at": latest_change_at,
        "source": _as_text(closure.get("source")) or _as_text(proposal_intent.get("source")) or _as_text(action_intent.get("source")),
        "zone_id": _as_text(closure.get("zone_id")) or _as_text(proposal_intent.get("zone_id")) or _as_text(action_intent.get("zone_id")),
        "module_id": _as_text(closure.get("module_id")) or _as_text(proposal_intent.get("module_id")) or _as_text(action_intent.get("module_id")),
        "action_id": _as_text(closure.get("action_id")),
        "action_intent_id": _as_text(action_intent.get("action_intent_id")) or _as_text(closure.get("action_id")),
        "closure_id": _as_text(closure.get("closure_id")),
        "closure_state": _as_text(closure.get("state")),
        "proposal_state": _as_text(proposal_intent.get("state")) or _as_text(closure.get("state")),
        "accepted_at": _as_text(closure.get("accepted_at")) or _as_text(proposal_intent.get("accepted_at")),
        "executed_at": _as_text(execution.get("executed_at")),
        "title": _as_text(proposal_intent.get("title")) or _as_text((closure.get("metadata") or {}).get("title")),
        "summary": _as_text(proposal_intent.get("summary")) or _as_text((closure.get("metadata") or {}).get("summary")),
        "confidence": proposal_intent.get("confidence"),
        "worker": {
            "claim_state": claim_state,
            "receipt_state": receipt_state,
            "settlement_state": settlement_state,
            "delivery_mode": _as_text((latest_claim or {}).get("delivery_mode")) or _as_text((latest_receipt or {}).get("delivery_mode")),
            "claim_id": _as_text((latest_claim or {}).get("claim_id")),
            "receipt_id": _as_text((latest_receipt or {}).get("receipt_id")),
            "reassignable": bool((latest_claim or {}).get("reassignable")) if latest_claim else False,
        },
    }


def _status_from_engine_proposal(proposal: Mapping[str, Any]) -> dict[str, Any] | None:
    proposal_id = _as_text(proposal.get("proposal_id"))
    if not proposal_id:
        return None

    latest_change_at = (
        _as_text(proposal.get("executed_at"))
        or _as_text(proposal.get("accepted_at"))
        or _as_text(proposal.get("created_at"))
    )

    return {
        "contract": "ProposalLifecycleStatusV1",
        "proposal_id": proposal_id,
        "lifecycle_status": _engine_lifecycle_status(proposal),
        "revision": 0,
        "latest_change_at": latest_change_at,
        "source": _as_text(proposal.get("source")) or "suggestion_engine",
        "zone_id": _engine_zone_id(proposal),
        "module_id": _engine_module_id(proposal),
        "action_id": None,
        "action_intent_id": _as_text(proposal.get("action_intent_id")),
        "closure_id": None,
        "closure_state": None,
        "proposal_state": _as_text(proposal.get("status")),
        "accepted_at": _as_text(proposal.get("accepted_at")),
        "executed_at": _as_text(proposal.get("executed_at")),
        "title": _as_text(proposal.get("title")) or _as_text(proposal.get("action_type")),
        "summary": _as_text(proposal.get("explanation")),
        "confidence": proposal.get("confidence"),
        "worker": {},
    }


def _status_matches_filters(
    item: Mapping[str, Any],
    *,
    proposal_id: str | None,
    zone_id: str | None,
    module_id: str | None,
    lifecycle_status: str | None,
) -> bool:
    if proposal_id and item.get("proposal_id") != proposal_id:
        return False
    if zone_id and item.get("zone_id") != zone_id:
        return False
    if module_id and item.get("module_id") != module_id:
        return False
    if lifecycle_status and item.get("lifecycle_status") != lifecycle_status:
        return False
    return True


def _sort_statuses(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (dict(item) for item in items),
        key=lambda item: (
            int(item.get("revision") or 0),
            item.get("latest_change_at") or "",
            item.get("proposal_id") or "",
        ),
        reverse=True,
    )


def _collect_status_payloads(
    *,
    store: ActionClosureStore,
    proposal_provider: Any | None = None,
    proposal_id: str | None = None,
    zone_id: str | None = None,
    module_id: str | None = None,
    lifecycle_status: str | None = None,
) -> list[dict[str, Any]]:
    status_index: dict[str, dict[str, Any]] = {}
    for closure in store.list():
        item = _status_from_closure(closure)
        if item is None:
            continue
        existing = status_index.get(item["proposal_id"])
        if existing is None or int(item.get("revision") or 0) >= int(existing.get("revision") or 0):
            status_index[item["proposal_id"]] = item

    if proposal_provider is not None and hasattr(proposal_provider, "get_proposals"):
        try:
            for proposal in proposal_provider.get_proposals(include_executed=True):
                item = _status_from_engine_proposal(proposal)
                if item is None:
                    continue
                status_index.setdefault(item["proposal_id"], item)
        except Exception:
            pass

    return _sort_statuses(
        [
            item
            for item in status_index.values()
            if _status_matches_filters(
                item,
                proposal_id=proposal_id,
                zone_id=zone_id,
                module_id=module_id,
                lifecycle_status=lifecycle_status,
            )
        ]
    )


def build_proposal_lifecycle_status_summary(
    store: ActionClosureStore | None = None,
    *,
    proposal_provider: Any | None = None,
    proposal_id: str | None = None,
    zone_id: str | None = None,
    module_id: str | None = None,
    lifecycle_status: str | None = None,
    recent_limit: int = 5,
    since_revision: int | None = None,
) -> ProposalLifecycleStatusSummaryReadModel:
    store = store or get_action_closure_store()
    items = _collect_status_payloads(
        store=store,
        proposal_provider=proposal_provider,
        proposal_id=proposal_id,
        zone_id=zone_id,
        module_id=module_id,
        lifecycle_status=lifecycle_status,
    )

    try:
        from copilot_core.api.v1.notifications import get_action_closure_follow_up_dispatch_store

        dispatch_store = get_action_closure_follow_up_dispatch_store()
        current_revision = max(
            int(store.get_current_revision() or 0),
            int(dispatch_store.get_current_claim_revision() or 0),
            int(dispatch_store.get_current_receipt_revision() or 0),
        )
    except Exception:
        current_revision = int(store.get_current_revision() or 0)

    delta_items = [item for item in items if since_revision is None or int(item.get("revision") or 0) > since_revision]

    lifecycle_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    zone_counter: Counter[str] = Counter()
    module_counter: Counter[str] = Counter()

    for item in items:
        lifecycle_counter[str(item.get("lifecycle_status") or "unknown")] += 1
        source = _as_text(item.get("source"))
        if source:
            source_counter[source] += 1
        zid = _as_text(item.get("zone_id"))
        if zid:
            zone_counter[zid] += 1
        mid = _as_text(item.get("module_id"))
        if mid:
            module_counter[mid] += 1

    latest_change_at = _latest_change_at(items)
    meta = ReadModelMeta(source="proposal_lifecycle", freshness=latest_change_at or ReadModelMeta().freshness)
    recent_statuses = [_compact_recent_status(item) for item in items[: max(1, recent_limit)]] if items else []

    highlights: list[str] = []
    if items:
        parts = [f"{len(items)} Proposals"]
        for status_name in ("suggested", "accepted", "executed", "failed", "follow_up_open", "settled"):
            count = lifecycle_counter.get(status_name, 0)
            if count:
                label = status_name.replace("_", "-")
                parts.append(f"{count} {label}")
        highlights.append(", ".join(parts))
        recent_line = _describe_recent_status(items[0])
        if recent_line:
            highlights.append(recent_line)

    return ProposalLifecycleStatusSummaryReadModel(
        meta=meta,
        revision=current_revision,
        latest_change_at=latest_change_at,
        total_proposals=len(items),
        lifecycle_statuses=_sort_counter(lifecycle_counter),
        sources=_sort_counter(source_counter),
        zones=_sort_counter(zone_counter),
        modules=_sort_counter(module_counter),
        recent_statuses=recent_statuses,
        highlights=highlights,
        delta=_build_delta_payload(
            delta_items,
            since_revision=since_revision,
            current_revision=current_revision,
            recent_limit=recent_limit,
        ),
    )


def get_proposal_lifecycle_status(
    proposal_id: str,
    *,
    store: ActionClosureStore | None = None,
    proposal_provider: Any | None = None,
) -> ProposalLifecycleStatus | None:
    store = store or get_action_closure_store()
    normalized_proposal_id = _as_text(proposal_id)
    if not normalized_proposal_id:
        return None

    items = _collect_status_payloads(
        store=store,
        proposal_provider=proposal_provider,
        proposal_id=normalized_proposal_id,
    )
    if not items:
        return None

    status_payload = items[0]
    meta = ReadModelMeta(
        source="proposal_lifecycle",
        freshness=status_payload.get("latest_change_at") or ReadModelMeta().freshness,
    )
    return ProposalLifecycleStatus(
        meta=meta,
        proposal_id=str(status_payload.get("proposal_id") or normalized_proposal_id),
        lifecycle_status=str(status_payload.get("lifecycle_status") or "unknown"),
        revision=int(status_payload.get("revision") or 0),
        latest_change_at=_as_text(status_payload.get("latest_change_at")),
        source=_as_text(status_payload.get("source")),
        zone_id=_as_text(status_payload.get("zone_id")),
        module_id=_as_text(status_payload.get("module_id")),
        action_id=_as_text(status_payload.get("action_id")),
        action_intent_id=_as_text(status_payload.get("action_intent_id")),
        closure_id=_as_text(status_payload.get("closure_id")),
        closure_state=_as_text(status_payload.get("closure_state")),
        proposal_state=_as_text(status_payload.get("proposal_state")),
        accepted_at=_as_text(status_payload.get("accepted_at")),
        executed_at=_as_text(status_payload.get("executed_at")),
        title=_as_text(status_payload.get("title")),
        summary=_as_text(status_payload.get("summary")),
        confidence=status_payload.get("confidence"),
        worker=dict(status_payload.get("worker") or {}),
    )


def describe_proposal_lifecycle_summary(summary: Mapping[str, Any]) -> str | None:
    total = int(summary.get("total_proposals") or 0)
    if total <= 0:
        return None

    counts = summary.get("lifecycle_statuses") or {}
    parts = [f"Proposal-Lifecycle: {total}"]
    for status_name, label in (
        ("suggested", "suggested"),
        ("accepted", "accepted"),
        ("executed", "executed"),
        ("failed", "failed"),
        ("follow_up_open", "follow-up-open"),
        ("settled", "settled"),
    ):
        count = int(counts.get(status_name) or 0)
        if count:
            parts.append(f"{count} {label}")
    return ", ".join(parts)


__all__ = [
    "ProposalLifecycleStatus",
    "ProposalLifecycleStatusSummaryReadModel",
    "build_proposal_lifecycle_status_summary",
    "get_proposal_lifecycle_status",
    "describe_proposal_lifecycle_summary",
]
