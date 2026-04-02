"""Contract tests for Zone Presence Hold / Release Surface (Slice 39).

Tests verify:
1. ZonePresenceHoldV1 contract structure
2. ZonePresenceHoldStore operations (set, release, get, summary)
3. Hold expiration logic
4. Hold state enforcement (force_on, force_off, auto)
5. Revision tracking and delta responses
"""
import pytest
from datetime import datetime, timezone, timedelta

from copilot_core.core.zone_presence_hold import (
    ZonePresenceHold,
    ZonePresenceHoldSummary,
    ZonePresenceHoldStore,
    ZoneHoldState,
    get_zone_presence_hold_store,
)


@pytest.fixture(autouse=True)
def clear_store():
    """Clear hold store before each test."""
    store = get_zone_presence_hold_store()
    store.clear()
    yield


class TestZonePresenceHoldContract:
    """Test ZonePresenceHoldV1 contract structure."""
    
    def test_hold_contract_fields(self):
        """Test ZonePresenceHold has all required fields."""
        hold = ZonePresenceHold(
            hold_id="hold_zone_living_001",
            zone_id="zone:living",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="manual",
        )
        
        assert hold.hold_id == "hold_zone_living_001"
        assert hold.zone_id == "zone:living"
        assert hold.hold_state == ZoneHoldState.FORCE_ON
        assert hold.reason == "manual"
        assert hold.set_at is not None
        assert hold.expires_at is None
        assert hold.released is False
        assert hold.released_at is None
        assert hold.released_reason is None
    
    def test_hold_to_dict(self):
        """Test ZonePresenceHold serialization."""
        hold = ZonePresenceHold(
            hold_id="hold_zone_living_002",
            zone_id="zone:bedroom",
            hold_state=ZoneHoldState.FORCE_OFF,
            reason="testing",
        )
        
        data = hold.to_dict()
        
        assert data["contract"] == "ZonePresenceHoldV1"
        assert data["hold_id"] == "hold_zone_living_002"
        assert data["zone_id"] == "zone:bedroom"
        assert data["hold_state"] == "force_off"
        assert data["reason"] == "testing"
        assert data["is_active"] is True
        assert data["is_expired"] is False
    
    def test_hold_with_expiry(self):
        """Test hold with expiration time."""
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(hours=1)).isoformat()
        
        hold = ZonePresenceHold(
            hold_id="hold_zone_kitchen_001",
            zone_id="zone:kitchen",
            hold_state=ZoneHoldState.FORCE_ON,
            expires_at=expires_at,
        )
        
        assert hold.expires_at == expires_at
        assert hold.is_expired() is False
        assert hold.is_active() is True
    
    def test_hold_is_active(self):
        """Test hold active state logic."""
        # Active hold
        hold = ZonePresenceHold(
            hold_id="hold_001",
            zone_id="zone:test",
            hold_state=ZoneHoldState.FORCE_ON,
        )
        assert hold.is_active() is True
        
        # Released hold
        hold_released = ZonePresenceHold(
            hold_id="hold_002",
            zone_id="zone:test",
            hold_state=ZoneHoldState.FORCE_ON,
            released=True,
            released_at=datetime.now(timezone.utc).isoformat(),
        )
        assert hold_released.is_active() is False
    
    def test_hold_is_expired(self):
        """Test hold expiration logic."""
        # Expired hold
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        hold_expired = ZonePresenceHold(
            hold_id="hold_003",
            zone_id="zone:test",
            hold_state=ZoneHoldState.FORCE_ON,
            expires_at=past,
        )
        assert hold_expired.is_expired() is True
        assert hold_expired.is_active() is False
        
        # Future expiry
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        hold_valid = ZonePresenceHold(
            hold_id="hold_004",
            zone_id="zone:test",
            hold_state=ZoneHoldState.FORCE_ON,
            expires_at=future,
        )
        assert hold_valid.is_expired() is False
        assert hold_valid.is_active() is True
    
    def test_hold_should_enforce(self):
        """Test hold enforcement logic."""
        # FORCE_ON should enforce
        hold_on = ZonePresenceHold(
            hold_id="hold_005",
            zone_id="zone:test",
            hold_state=ZoneHoldState.FORCE_ON,
        )
        assert hold_on.should_enforce() is True
        
        # FORCE_OFF should enforce
        hold_off = ZonePresenceHold(
            hold_id="hold_006",
            zone_id="zone:test",
            hold_state=ZoneHoldState.FORCE_OFF,
        )
        assert hold_off.should_enforce() is True
        
        # AUTO should not enforce
        hold_auto = ZonePresenceHold(
            hold_id="hold_007",
            zone_id="zone:test",
            hold_state=ZoneHoldState.AUTO,
        )
        assert hold_auto.should_enforce() is False
        
        # Expired hold should not enforce
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        hold_expired = ZonePresenceHold(
            hold_id="hold_008",
            zone_id="zone:test",
            hold_state=ZoneHoldState.FORCE_ON,
            expires_at=past,
        )
        assert hold_expired.should_enforce() is False


class TestZonePresenceHoldStore:
    """Test ZonePresenceHoldStore operations."""
    
    def test_set_hold_creates_hold(self):
        """Test setting a hold creates a hold record."""
        store = get_zone_presence_hold_store()
        
        hold = store.set_hold(
            zone_id="zone:living",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="manual",
        )
        
        assert hold.hold_id is not None
        assert hold.zone_id == "zone:living"
        assert hold.hold_state == ZoneHoldState.FORCE_ON
        assert hold.reason == "manual"
        assert hold.released is False
    
    def test_set_hold_with_duration(self):
        """Test setting a hold with auto-expiry."""
        store = get_zone_presence_hold_store()
        
        hold = store.set_hold(
            zone_id="zone:bedroom",
            hold_state=ZoneHoldState.FORCE_OFF,
            duration_seconds=3600,  # 1 hour
        )
        
        assert hold.expires_at is not None
        assert hold.is_expired() is False
    
    def test_set_hold_updates_existing(self):
        """Test updating an existing hold."""
        store = get_zone_presence_hold_store()
        
        # Initial hold
        hold1 = store.set_hold(
            zone_id="zone:kitchen",
            hold_state=ZoneHoldState.FORCE_ON,
            reason="initial",
        )
        
        # Update hold
        hold2 = store.set_hold(
            zone_id="zone:kitchen",
            hold_state=ZoneHoldState.FORCE_OFF,
            reason="updated",
        )
        
        assert hold2.hold_id == hold1.hold_id  # Same hold updated
        assert hold2.hold_state == ZoneHoldState.FORCE_OFF
        assert hold2.reason == "updated"
    
    def test_release_hold(self):
        """Test releasing a hold."""
        store = get_zone_presence_hold_store()
        
        # Set hold
        store.set_hold(
            zone_id="zone:living",
            hold_state=ZoneHoldState.FORCE_ON,
        )
        
        # Release hold
        released = store.release_hold(
            zone_id="zone:living",
            reason="manual_release",
        )
        
        assert released is True
        
        # Verify hold is released
        hold = store.get_hold_by_zone("zone:living")
        assert hold is not None
        assert hold.released is True
        assert hold.released_reason == "manual_release"
        assert hold.hold_state == ZoneHoldState.AUTO
    
    def test_release_nonexistent_hold(self):
        """Test releasing a hold that doesn't exist."""
        store = get_zone_presence_hold_store()
        
        released = store.release_hold(zone_id="zone:nonexistent")
        
        assert released is False
    
    def test_get_hold_by_zone(self):
        """Test getting hold by zone ID."""
        store = get_zone_presence_hold_store()
        
        store.set_hold(
            zone_id="zone:bedroom",
            hold_state=ZoneHoldState.FORCE_ON,
        )
        
        hold = store.get_hold_by_zone("zone:bedroom")
        
        assert hold is not None
        assert hold.zone_id == "zone:bedroom"
        assert hold.hold_state == ZoneHoldState.FORCE_ON
    
    def test_get_hold_by_zone_not_found(self):
        """Test getting hold for zone without hold."""
        store = get_zone_presence_hold_store()
        
        hold = store.get_hold_by_zone("zone:nonexistent")
        
        assert hold is None
    
    def test_get_active_hold_state(self):
        """Test getting effective hold state."""
        store = get_zone_presence_hold_store()
        
        # No hold -> AUTO
        state = store.get_active_hold_state("zone:test")
        assert state == ZoneHoldState.AUTO
        
        # FORCE_ON hold
        store.set_hold(
            zone_id="zone:test",
            hold_state=ZoneHoldState.FORCE_ON,
        )
        state = store.get_active_hold_state("zone:test")
        assert state == ZoneHoldState.FORCE_ON
        
        # Released hold -> AUTO
        store.release_hold(zone_id="zone:test")
        state = store.get_active_hold_state("zone:test")
        assert state == ZoneHoldState.AUTO
    
    def test_get_hold_summary(self):
        """Test hold summary aggregation."""
        store = get_zone_presence_hold_store()
        
        # Create multiple holds
        store.set_hold(zone_id="zone:living", hold_state=ZoneHoldState.FORCE_ON)
        store.set_hold(zone_id="zone:bedroom", hold_state=ZoneHoldState.FORCE_OFF)
        store.set_hold(zone_id="zone:kitchen", hold_state=ZoneHoldState.AUTO)
        
        summary = store.get_hold_summary()
        
        assert summary.hold_revision > 0
        assert summary.total_holds == 3
        assert summary.active_holds == 3
        assert summary.force_on_holds == 1
        assert summary.force_off_holds == 1
        assert summary.auto_holds == 1
        assert summary.has_changes is True
    
    def test_hold_summary_delta(self):
        """Test hold summary delta with since_revision."""
        store = get_zone_presence_hold_store()
        
        # Initial state
        store.set_hold(zone_id="zone:living", hold_state=ZoneHoldState.FORCE_ON)
        summary1 = store.get_hold_summary()
        
        # No changes
        summary2 = store.get_hold_summary(since_revision=summary1.hold_revision)
        assert summary2.has_changes is False
        
        # New hold
        store.set_hold(zone_id="zone:bedroom", hold_state=ZoneHoldState.FORCE_OFF)
        summary3 = store.get_hold_summary(since_revision=summary1.hold_revision)
        assert summary3.has_changes is True
    
    def test_revision_tracking(self):
        """Test revision increments on changes."""
        store = get_zone_presence_hold_store()
        
        rev1 = store.get_revision()
        
        store.set_hold(zone_id="zone:test", hold_state=ZoneHoldState.FORCE_ON)
        rev2 = store.get_revision()
        
        store.release_hold(zone_id="zone:test")
        rev3 = store.get_revision()
        
        assert rev2 > rev1
        assert rev3 > rev2
    
    def test_get_all_holds(self):
        """Test getting all holds with filtering."""
        store = get_zone_presence_hold_store()
        
        store.set_hold(zone_id="zone:living", hold_state=ZoneHoldState.FORCE_ON)
        store.set_hold(zone_id="zone:bedroom", hold_state=ZoneHoldState.FORCE_OFF)
        store.set_hold(zone_id="zone:kitchen", hold_state=ZoneHoldState.FORCE_ON)
        
        # Get all
        all_holds = store.get_all_holds()
        assert len(all_holds) == 3
        
        # Get by zone
        living_holds = store.get_all_holds(zone_id="zone:living")
        assert len(living_holds) == 1
        assert living_holds[0].zone_id == "zone:living"
        
        # Get active only
        store.release_hold(zone_id="zone:bedroom")
        active_holds = store.get_all_holds(active_only=True)
        assert len(active_holds) == 2


class TestZoneHoldStateEnum:
    """Test ZoneHoldState enum values."""
    
    def test_hold_states(self):
        """Test all hold state values."""
        assert ZoneHoldState.AUTO.value == "auto"
        assert ZoneHoldState.FORCE_ON.value == "force_on"
        assert ZoneHoldState.FORCE_OFF.value == "force_off"
    
    def test_hold_state_from_string(self):
        """Test creating hold state from string."""
        assert ZoneHoldState("auto") == ZoneHoldState.AUTO
        assert ZoneHoldState("force_on") == ZoneHoldState.FORCE_ON
        assert ZoneHoldState("force_off") == ZoneHoldState.FORCE_OFF
