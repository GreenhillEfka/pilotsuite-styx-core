"""
Proposal Lifecycle Read Model — Zone-Scoped Feed (Slice 34)

Provides zone-scoped proposal lifecycle feeds for dashboard pollers and system contexts.
All data is derived from canonical Proposal/Action/Closure/Settlement truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from copilot_core.automations.suggestion_engine import AutomationSuggestionEngine
from copilot_core.core.proposal_lifecycle_store import ProposalLifecycleStore
from copilot_core.core.proposal_lifecycle_read_model import ProposalLifecycleStatus


@dataclass
class ZoneProposalFeedEntryV1:
    """Single zone-scoped proposal feed entry."""

    proposal_id: str
    zone_id: str
    zone_name: str | None
    status: str  # suggested | accepted | executed | failed | follow_up_open | settled
    title: str
    summary: str
    created_at: str
    updated_at: str
    revision: int
    source: str  # predictive | habitus | voice | multizone
    confidence: float | None = None
    action_closure_id: str | None = None
    follow_up_dispatch_id: str | None = None


@dataclass
class ZoneProposalFeedV1:
    """Zone-scoped proposal feed for dashboard pollers."""

    zone_id: str
    zone_name: str | None
    proposals: list[ZoneProposalFeedEntryV1] = field(default_factory=list)
    revision: int = 0
    latest_change_at: str | None = None
    has_pending: bool = False
    has_failed: bool = False
    has_follow_up_open: bool = False


@dataclass
class ZoneProposalFeedSummaryV1:
    """Summary of zone-scoped proposal feeds."""

    zones: list[ZoneProposalFeedV1] = field(default_factory=list)
    revision: int = 0
    latest_change_at: str | None = None
    total_proposals: int = 0
    zones_with_pending: int = 0
    zones_with_failed: int = 0
    zones_with_follow_up: int = 0


class ZoneProposalFeedStore:
    """Zone-scoped proposal feed store."""

    def __init__(self, suggestion_engine: AutomationSuggestionEngine):
        self.suggestion_engine = suggestion_engine
        self._revision = 0

    def build_zone_feed(self, zone_id: str, zone_name: str | None = None) -> ZoneProposalFeedV1:
        """Build zone-scoped proposal feed from canonical truth."""
        lifecycle_store = ProposalLifecycleStore(self.suggestion_engine)
        all_statuses = lifecycle_store.list_statuses()

        zone_proposals = [
            status for status in all_statuses
            if status.zone_id == zone_id
        ]

        entries = []
        has_pending = False
        has_failed = False
        has_follow_up_open = False
        latest_change_at: str | None = None
        max_revision = 0

        for status in zone_proposals:
            entry = ZoneProposalFeedEntryV1(
                proposal_id=status.proposal_id,
                zone_id=status.zone_id or zone_id,
                zone_name=zone_name,
                status=status.lifecycle_status,
                title=status.title or "",
                summary=status.summary or "",
                created_at=status.latest_change_at or "",
                updated_at=status.latest_change_at or "",
                revision=status.revision,
                source=status.source or "unknown",
                confidence=status.confidence,
                action_closure_id=status.closure_id,
                follow_up_dispatch_id=None,
            )
            entries.append(entry)

            if status.lifecycle_status == "suggested":
                has_pending = True
            elif status.lifecycle_status == "failed":
                has_failed = True
            elif status.lifecycle_status == "follow_up_open":
                has_follow_up_open = True

            if status.latest_change_at:
                if latest_change_at is None or status.latest_change_at > latest_change_at:
                    latest_change_at = status.latest_change_at

            if status.revision > max_revision:
                max_revision = status.revision

        self._revision = max(self._revision, max_revision)

        return ZoneProposalFeedV1(
            zone_id=zone_id,
            zone_name=zone_name,
            proposals=entries,
            revision=self._revision,
            latest_change_at=latest_change_at,
            has_pending=has_pending,
            has_failed=has_failed,
            has_follow_up_open=has_follow_up_open,
        )

    def build_zone_feed_summary(
        self,
        zone_ids: list[str] | None = None,
        zone_names: dict[str, str] | None = None,
    ) -> ZoneProposalFeedSummaryV1:
        """Build summary of zone-scoped proposal feeds."""
        lifecycle_store = ProposalLifecycleStore(self.suggestion_engine)
        all_statuses = lifecycle_store.list_statuses()

        if zone_ids:
            all_statuses = [s for s in all_statuses if s.zone_id in zone_ids]

        zone_proposal_map: dict[str, list[ProposalLifecycleStatus]] = {}
        for status in all_statuses:
            if status.zone_id not in zone_proposal_map:
                zone_proposal_map[status.zone_id] = []
            zone_proposal_map[status.zone_id].append(status)

        zone_feeds = []
        total_proposals = 0
        zones_with_pending = 0
        zones_with_failed = 0
        zones_with_follow_up = 0
        global_max_revision = 0
        global_latest_change_at: str | None = None

        for zone_id, proposals in zone_proposal_map.items():
            zone_name = zone_names.get(zone_id) if zone_names else None

            has_pending = any(p.lifecycle_status == "suggested" for p in proposals)
            has_failed = any(p.lifecycle_status == "failed" for p in proposals)
            has_follow_up = any(p.lifecycle_status == "follow_up_open" for p in proposals)

            zone_revision = max((p.revision for p in proposals), default=0)
            zone_latest = max(
                (p.latest_change_at for p in proposals if p.latest_change_at),
                default=None,
            )

            entries = [
                ZoneProposalFeedEntryV1(
                    proposal_id=p.proposal_id,
                    zone_id=p.zone_id or zone_id,
                    zone_name=zone_name,
                    status=p.lifecycle_status,
                    title=p.title or "",
                    summary=p.summary or "",
                    created_at=p.latest_change_at or "",
                    updated_at=p.latest_change_at or "",
                    revision=p.revision,
                    source=p.source or "unknown",
                    confidence=p.confidence,
                    action_closure_id=p.closure_id,
                    follow_up_dispatch_id=None,
                )
                for p in proposals
            ]

            zone_feed = ZoneProposalFeedV1(
                zone_id=zone_id,
                zone_name=zone_name,
                proposals=entries,
                revision=zone_revision,
                latest_change_at=zone_latest,
                has_pending=has_pending,
                has_failed=has_failed,
                has_follow_up_open=has_follow_up,
            )
            zone_feeds.append(zone_feed)

            total_proposals += len(proposals)
            if has_pending:
                zones_with_pending += 1
            if has_failed:
                zones_with_failed += 1
            if has_follow_up:
                zones_with_follow_up += 1

            if zone_revision > global_max_revision:
                global_max_revision = zone_revision
            if zone_latest:
                if global_latest_change_at is None or zone_latest > global_latest_change_at:
                    global_latest_change_at = zone_latest

        self._revision = max(self._revision, global_max_revision)

        return ZoneProposalFeedSummaryV1(
            zones=zone_feeds,
            revision=self._revision,
            latest_change_at=global_latest_change_at,
            total_proposals=total_proposals,
            zones_with_pending=zones_with_pending,
            zones_with_failed=zones_with_failed,
            zones_with_follow_up=zones_with_follow_up,
        )
