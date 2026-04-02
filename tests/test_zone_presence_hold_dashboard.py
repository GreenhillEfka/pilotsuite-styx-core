"""Zone Presence Hold Dashboard Integration Tests — Slice 41.

Tests that Zone Presence Hold state is correctly exposed in the Zone Dashboard API.
Validates that _collect_praesenz includes hold_state, hold_reason, hold_enforced fields.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from copilot_core.core.zone_presence_hold import (
    ZonePresenceHoldStore,
    ZoneHoldState,
    get_zone_presence_hold_store,
)


class TestZonePresenceHoldDashboardIntegration:
    """Test hold state integration with dashboard presence collection."""
    
    @pytest.fixture(autouse=True)
    def reset_global_store(self):
        """Reset the global hold store before each test."""
        store = get_zone_presence_hold_store()
        store.clear()
        yield
        store.clear()
    
    @pytest.fixture
    def hold_store(self):
        """Get the global hold store."""
        return get_zone_presence_hold_store()
    
    @pytest.fixture
    def zone_id(self):
        return "zone_living_room"
    
    def test_hold_store_available_for_dashboard(self):
        """Verify hold store is available for dashboard integration."""
        store = get_zone_presence_hold_store()
        assert store is not None
        assert isinstance(store, ZonePresenceHoldStore)
    
    def test_collect_praesenz_includes_hold_state_when_active(
        self, hold_store, zone_id
    ):
        """Test _collect_praesenz includes hold_state when hold is active."""
        from copilot_core.api.v1.zone_dashboard import _collect_praesenz, _svc
        
        # Set up hold
        hold_store.set_hold(zone_id, ZoneHoldState.FORCE_ON, reason="dashboard_test")
        
        # Mock hub_praesenz service
        mock_hub = MagicMock()
        mock_presence = MagicMock()
        mock_presence.is_occupied = True
        mock_presence.person_count = 2
        mock_presence.persons = ["person_1", "person_2"]
        mock_presence.last_entered = datetime.now(timezone.utc)
        mock_presence.last_left = None
        mock_presence.occupied_since = datetime.now(timezone.utc)
        mock_presence.sources_active = 2
        mock_presence.sources_total = 3
        mock_hub.get_zone_presence.return_value = mock_presence
        
        # Temporarily wire the service
        old_hub = _svc.get("hub_praesenz")
        _svc["hub_praesenz"] = mock_hub
        
        try:
            result = _collect_praesenz(zone_id)
            
            assert result is not None
            assert result["hold_state"] == "force_on"
            assert result["hold_reason"] == "dashboard_test"
            assert result["hold_enforced"] is True
            assert "hold_set_at" in result
        finally:
            # Restore old service
            if old_hub:
                _svc["hub_praesenz"] = old_hub
            else:
                _svc.pop("hub_praesenz", None)
    
    def test_collect_praesenz_hold_state_auto_when_no_hold(
        self, hold_store, zone_id
    ):
        """Test _collect_praesenz returns hold_state=auto when no hold."""
        from copilot_core.api.v1.zone_dashboard import _collect_praesenz, _svc
        
        # No hold set
        
        # Mock hub_praesenz service
        mock_hub = MagicMock()
        mock_presence = MagicMock()
        mock_presence.is_occupied = False
        mock_presence.person_count = 0
        mock_presence.persons = []
        mock_presence.last_entered = None
        mock_presence.last_left = None
        mock_presence.occupied_since = None
        mock_presence.sources_active = 0
        mock_presence.sources_total = 3
        mock_hub.get_zone_presence.return_value = mock_presence
        
        # Temporarily wire the service
        old_hub = _svc.get("hub_praesenz")
        _svc["hub_praesenz"] = mock_hub
        
        try:
            result = _collect_praesenz(zone_id)
            
            assert result is not None
            assert result["hold_state"] == "auto"
            assert result["hold_enforced"] is False
        finally:
            if old_hub:
                _svc["hub_praesenz"] = old_hub
            else:
                _svc.pop("hub_praesenz", None)
    
    def test_collect_praesenz_force_off_hold(self, hold_store, zone_id):
        """Test _collect_praesenz with FORCE_OFF hold."""
        from copilot_core.api.v1.zone_dashboard import _collect_praesenz, _svc
        
        # Set up FORCE_OFF hold
        hold_store.set_hold(zone_id, ZoneHoldState.FORCE_OFF, reason="vacation")
        
        # Mock hub_praesenz service
        mock_hub = MagicMock()
        mock_presence = MagicMock()
        mock_presence.is_occupied = True  # Sensor says occupied
        mock_presence.person_count = 1
        mock_hub.get_zone_presence.return_value = mock_presence
        
        old_hub = _svc.get("hub_praesenz")
        _svc["hub_praesenz"] = mock_hub
        
        try:
            result = _collect_praesenz(zone_id)
            
            assert result is not None
            assert result["hold_state"] == "force_off"
            assert result["hold_reason"] == "vacation"
            assert result["hold_enforced"] is True
        finally:
            if old_hub:
                _svc["hub_praesenz"] = old_hub
            else:
                _svc.pop("hub_praesenz", None)
    
    def test_collect_praesenz_hold_released_not_included(
        self, hold_store, zone_id
    ):
        """Test released hold is not included in dashboard data."""
        from copilot_core.api.v1.zone_dashboard import _collect_praesenz, _svc
        
        # Set up hold then release it
        hold_store.set_hold(zone_id, ZoneHoldState.FORCE_ON, reason="temp_hold")
        hold_store.release_hold(zone_id, reason="test_release")
        
        # Mock hub_praesenz service
        mock_hub = MagicMock()
        mock_presence = MagicMock()
        mock_presence.is_occupied = False
        mock_presence.person_count = 0
        mock_hub.get_zone_presence.return_value = mock_presence
        
        old_hub = _svc.get("hub_praesenz")
        _svc["hub_praesenz"] = mock_hub
        
        try:
            result = _collect_praesenz(zone_id)
            
            assert result is not None
            # Released hold should not be shown as active
            assert result["hold_state"] == "auto"
            assert result["hold_enforced"] is False
        finally:
            if old_hub:
                _svc["hub_praesenz"] = old_hub
            else:
                _svc.pop("hub_praesenz", None)
    
    def test_collect_praesenz_hold_expires_at_included(self, hold_store, zone_id):
        """Test hold_expires_at is included when hold has expiration."""
        from copilot_core.api.v1.zone_dashboard import _collect_praesenz, _svc
        from datetime import timedelta
        
        # Set up hold with 1-hour expiration
        hold_store.set_hold(
            zone_id,
            ZoneHoldState.FORCE_ON,
            reason="timed_hold",
            duration_seconds=3600,
        )
        
        # Mock hub_praesenz service
        mock_hub = MagicMock()
        mock_presence = MagicMock()
        mock_presence.is_occupied = False
        mock_presence.person_count = 0
        mock_hub.get_zone_presence.return_value = mock_presence
        
        old_hub = _svc.get("hub_praesenz")
        _svc["hub_praesenz"] = mock_hub
        
        try:
            result = _collect_praesenz(zone_id)
            
            assert result is not None
            assert result["hold_state"] == "force_on"
            assert result["hold_expires_at"] is not None
            assert result["hold_enforced"] is True
        finally:
            if old_hub:
                _svc["hub_praesenz"] = old_hub
            else:
                _svc.pop("hub_praesenz", None)
    
    def test_collect_praesenz_graceful_degradation_on_store_error(
        self, zone_id
    ):
        """Test _collect_praesenz gracefully handles hold store errors."""
        from copilot_core.api.v1.zone_dashboard import _collect_praesenz, _svc
        
        # Mock hub_praesenz service
        mock_hub = MagicMock()
        mock_presence = MagicMock()
        mock_presence.is_occupied = True
        mock_presence.person_count = 1
        mock_hub.get_zone_presence.return_value = mock_presence
        
        # Mock hold store to raise exception
        with patch(
            "copilot_core.api.v1.zone_dashboard.get_zone_presence_hold_store",
            side_effect=Exception("Store unavailable"),
        ):
            old_hub = _svc.get("hub_praesenz")
            _svc["hub_praesenz"] = mock_hub
            
            try:
                result = _collect_praesenz(zone_id)
                
                # Should still return data with auto hold state
                assert result is not None
                assert result["hold_state"] == "auto"
                assert result["hold_enforced"] is False
                assert result["is_occupied"] is True
            finally:
                if old_hub:
                    _svc["hub_praesenz"] = old_hub
                else:
                    _svc.pop("hub_praesenz", None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
