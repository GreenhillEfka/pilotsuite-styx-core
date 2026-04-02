"""Zone Presence Hold / Release Surface for Slice 39.

Enables deterministic zone presence hold/release so presence recognition
does not flicker on short absence windows. Provides canonical hold state
tracking with expiration, reason tracking, and zone-scoped hold visibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, Dict, List
from enum import Enum


class ZoneHoldState(Enum):
    """Zone presence hold states."""
    AUTO = "auto"  # Normal aggregation (no hold)
    FORCE_ON = "force_on"  # Zone always occupied
    FORCE_OFF = "force_off"  # Zone always empty


@dataclass
class ZonePresenceHold:
    """Single zone presence hold record."""
    hold_id: str
    zone_id: str
    hold_state: ZoneHoldState
    reason: str = "manual"
    set_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str | None = None  # Optional auto-expiry
    released: bool = False
    released_at: str | None = None
    released_reason: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ZonePresenceHoldV1",
            "hold_id": self.hold_id,
            "zone_id": self.zone_id,
            "hold_state": self.hold_state.value,
            "reason": self.reason,
            "set_at": self.set_at,
            "expires_at": self.expires_at,
            "released": self.released,
            "released_at": self.released_at,
            "released_reason": self.released_reason,
            "is_active": self.is_active(),
            "is_expired": self.is_expired(),
        }
    
    def is_active(self) -> bool:
        """Check if hold is still active (not released, not expired)."""
        if self.released:
            return False
        return not self.is_expired()
    
    def is_expired(self) -> bool:
        """Check if hold has expired."""
        if not self.expires_at:
            return False
        now = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        return now > expires
    
    def should_enforce(self) -> bool:
        """Check if hold should be enforced (active and not auto)."""
        return self.is_active() and self.hold_state != ZoneHoldState.AUTO


@dataclass
class ZonePresenceHoldSummary:
    """Aggregated hold summary for zone presence."""
    hold_revision: int = 0
    latest_change_at: str | None = None
    total_holds: int = 0
    active_holds: int = 0
    expired_holds: int = 0
    released_holds: int = 0
    force_on_holds: int = 0
    force_off_holds: int = 0
    auto_holds: int = 0
    by_zone: dict[str, ZoneHoldState] = field(default_factory=dict)
    recent_holds: list[ZonePresenceHold] = field(default_factory=list)
    has_changes: bool = False
    since_revision: int | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "ZonePresenceHoldSummaryV1",
            "hold_revision": self.hold_revision,
            "latest_change_at": self.latest_change_at,
            "total_holds": self.total_holds,
            "active_holds": self.active_holds,
            "expired_holds": self.expired_holds,
            "released_holds": self.released_holds,
            "force_on_holds": self.force_on_holds,
            "force_off_holds": self.force_off_holds,
            "auto_holds": self.auto_holds,
            "by_zone": {k: v.value for k, v in self.by_zone.items()},
            "recent_holds": [h.to_dict() for h in self.recent_holds],
            "has_changes": self.has_changes,
            "since_revision": self.since_revision,
        }


class ZonePresenceHoldStore:
    """In-memory store for zone presence hold tracking."""
    
    def __init__(self) -> None:
        self._holds: dict[str, dict[str, Any]] = {}  # hold_id -> hold data
        self._by_zone: dict[str, str] = {}  # zone_id -> hold_id (latest)
        self._revision = 0
        self._latest_change_at: str | None = None
    
    def clear(self) -> None:
        """Clear all store data."""
        self._holds.clear()
        self._by_zone.clear()
        self._revision = 0
        self._latest_change_at = None
    
    def set_hold(
        self,
        zone_id: str,
        hold_state: ZoneHoldState,
        reason: str = "manual",
        duration_seconds: int | None = None,
    ) -> ZonePresenceHold:
        """Set or update zone presence hold.
        
        Returns:
            The created/updated ZonePresenceHold.
        """
        now = datetime.now(timezone.utc)
        
        # Check existing hold for zone
        existing_hold_id = self._by_zone.get(zone_id)
        if existing_hold_id:
            existing = self._holds.get(existing_hold_id)
            if existing and not existing.get("released", False):
                # Update existing hold
                expires_at = None
                if duration_seconds:
                    expires_at = (now + timedelta(seconds=duration_seconds)).isoformat()
                
                existing["hold_state"] = hold_state.value
                existing["reason"] = reason
                existing["expires_at"] = expires_at
                existing["updated_at"] = now.isoformat()
                
                self._revision += 1
                self._latest_change_at = now.isoformat()
                
                return self.get_hold(existing_hold_id)
        
        # Create new hold
        hold_id = f"hold_{zone_id}_{self._revision}"
        expires_at = None
        if duration_seconds:
            expires_at = (now + timedelta(seconds=duration_seconds)).isoformat()
        
        hold = ZonePresenceHold(
            hold_id=hold_id,
            zone_id=zone_id,
            hold_state=hold_state,
            reason=reason,
            set_at=now.isoformat(),
            expires_at=expires_at,
        )
        
        self._holds[hold_id] = {
            "hold_id": hold_id,
            "zone_id": zone_id,
            "hold_state": hold_state.value,
            "reason": reason,
            "set_at": now.isoformat(),
            "expires_at": expires_at,
            "released": False,
            "released_at": None,
            "released_reason": None,
        }
        
        self._by_zone[zone_id] = hold_id
        
        self._revision += 1
        self._latest_change_at = now.isoformat()
        
        return hold
    
    def release_hold(
        self,
        zone_id: str,
        reason: str = "manual_release",
    ) -> bool:
        """Release zone presence hold (reset to auto).
        
        Returns:
            True if hold was released, False if no active hold existed.
        """
        hold_id = self._by_zone.get(zone_id)
        if not hold_id:
            return False
        
        hold = self._holds.get(hold_id)
        if not hold or hold.get("released", False):
            return False
        
        now = datetime.now(timezone.utc).isoformat()
        hold["released"] = True
        hold["released_at"] = now
        hold["released_reason"] = reason
        hold["hold_state"] = ZoneHoldState.AUTO.value
        
        self._revision += 1
        self._latest_change_at = now
        
        return True
    
    def get_hold(self, hold_id: str) -> ZonePresenceHold | None:
        """Get a single hold by ID."""
        data = self._holds.get(hold_id)
        if not data:
            return None
        
        return ZonePresenceHold(
            hold_id=data["hold_id"],
            zone_id=data["zone_id"],
            hold_state=ZoneHoldState(data["hold_state"]),
            reason=data.get("reason", "manual"),
            set_at=data["set_at"],
            expires_at=data.get("expires_at"),
            released=data.get("released", False),
            released_at=data.get("released_at"),
            released_reason=data.get("released_reason"),
        )
    
    def get_hold_by_zone(self, zone_id: str) -> ZonePresenceHold | None:
        """Get current hold for a zone."""
        hold_id = self._by_zone.get(zone_id)
        if not hold_id:
            return None
        return self.get_hold(hold_id)
    
    def get_active_hold_state(self, zone_id: str) -> ZoneHoldState:
        """Get effective hold state for a zone (AUTO if no active hold)."""
        hold = self.get_hold_by_zone(zone_id)
        if hold and hold.should_enforce():
            return hold.hold_state
        return ZoneHoldState.AUTO
    
    def get_all_holds(
        self,
        limit: int = 50,
        zone_id: str | None = None,
        active_only: bool = False,
    ) -> list[ZonePresenceHold]:
        """Get holds with optional filtering."""
        holds = list(self._holds.values())
        
        if zone_id:
            holds = [h for h in holds if h.get("zone_id") == zone_id]
        
        if active_only:
            now = datetime.now(timezone.utc)
            filtered = []
            for h in holds:
                if h.get("released", False):
                    continue
                expires_at = h.get("expires_at")
                if expires_at:
                    exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if now > exp:
                        continue
                filtered.append(h)
            holds = filtered
        
        # Sort by set_at descending and limit
        holds.sort(key=lambda h: h.get("set_at", ""), reverse=True)
        holds = holds[:limit]
        
        return [
            ZonePresenceHold(
                hold_id=h["hold_id"],
                zone_id=h["zone_id"],
                hold_state=ZoneHoldState(h["hold_state"]),
                reason=h.get("reason", "manual"),
                set_at=h["set_at"],
                expires_at=h.get("expires_at"),
                released=h.get("released", False),
                released_at=h.get("released_at"),
                released_reason=h.get("released_reason"),
            )
            for h in holds
        ]
    
    def get_hold_summary(
        self,
        since_revision: int | None = None,
        recent_limit: int = 10,
        zone_id: str | None = None,
    ) -> ZonePresenceHoldSummary:
        """Get aggregated hold summary."""
        now = datetime.now(timezone.utc)
        
        # Get filtered holds
        holds = self.get_all_holds(limit=100, zone_id=zone_id)
        
        # Count states
        active_count = 0
        expired_count = 0
        released_count = 0
        force_on_count = 0
        force_off_count = 0
        auto_count = 0
        
        by_zone: dict[str, ZoneHoldState] = {}
        
        for hold in holds:
            if hold.hold_state == ZoneHoldState.FORCE_ON:
                force_on_count += 1
            elif hold.hold_state == ZoneHoldState.FORCE_OFF:
                force_off_count += 1
            else:
                auto_count += 1
            
            if hold.released:
                released_count += 1
            elif hold.is_expired():
                expired_count += 1
            else:
                active_count += 1
                # Track latest active hold per zone
                by_zone[hold.zone_id] = hold.hold_state
        
        has_changes = since_revision is None or self._revision > since_revision
        
        return ZonePresenceHoldSummary(
            hold_revision=self._revision,
            latest_change_at=self._latest_change_at,
            total_holds=len(holds),
            active_holds=active_count,
            expired_holds=expired_count,
            released_holds=released_count,
            force_on_holds=force_on_count,
            force_off_holds=force_off_count,
            auto_holds=auto_count,
            by_zone=by_zone,
            recent_holds=holds[:recent_limit],
            has_changes=has_changes,
            since_revision=since_revision,
        )
    
    def get_revision(self) -> int:
        """Get current revision."""
        return self._revision


_zone_presence_hold_store: Optional[ZonePresenceHoldStore] = None


def get_zone_presence_hold_store() -> ZonePresenceHoldStore:
    """Get or create the zone presence hold store."""
    global _zone_presence_hold_store
    if _zone_presence_hold_store is None:
        _zone_presence_hold_store = ZonePresenceHoldStore()
    return _zone_presence_hold_store
