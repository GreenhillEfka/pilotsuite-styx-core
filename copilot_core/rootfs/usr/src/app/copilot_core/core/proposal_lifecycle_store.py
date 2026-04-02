"""Proposal Lifecycle Store — thin wrapper around SuggestionEngine for lifecycle queries."""

from __future__ import annotations

from typing import Any

from copilot_core.automations.suggestion_engine import AutomationSuggestionEngine
from copilot_core.core.proposal_lifecycle_read_model import ProposalLifecycleStatus


class ProposalLifecycleStore:
    """Proposal lifecycle store backed by SuggestionEngine."""

    def __init__(self, suggestion_engine: AutomationSuggestionEngine):
        self.suggestion_engine = suggestion_engine

    def list_statuses(self) -> list[ProposalLifecycleStatus]:
        """List all proposal lifecycle statuses."""
        # Delegate to suggestion engine's lifecycle read model
        if hasattr(self.suggestion_engine, 'get_lifecycle_statuses'):
            return self.suggestion_engine.get_lifecycle_statuses()
        
        # Fallback: return empty list if method not available
        return []

    def get_status(self, proposal_id: str) -> ProposalLifecycleStatus | None:
        """Get lifecycle status for a specific proposal."""
        statuses = self.list_statuses()
        for status in statuses:
            if status.proposal_id == proposal_id:
                return status
        return None

    def list_statuses_by_zone(self, zone_id: str) -> list[ProposalLifecycleStatus]:
        """List lifecycle statuses filtered by zone."""
        statuses = self.list_statuses()
        return [s for s in statuses if s.zone_id == zone_id]
