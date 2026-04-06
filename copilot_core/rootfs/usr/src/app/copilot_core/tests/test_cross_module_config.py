"""Tests for cross-module configuration layer."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from copilot_core.config.cross_module import (
    CrossModuleConfig,
    ZoneConfig,
    SonosConfig,
    LightConfig,
    PresenceConfig,
    AlarmConfig,
    MoodConfig,
    Conflict,
)


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_area_registry():
    """Mock area registry with test areas."""
    reg = MagicMock()
    reg.areas = {
        "wohnbereich": MagicMock(id="wohnbereich", name="Wohnbereich"),
        "schlafzimmer": MagicMock(id="schlafzimmer", name="Schlafzimmer"),
        "kueche": MagicMock(id="kueche", name="Küche"),
    }
    return reg


@pytest.fixture
def mock_entity_registry():
    """Mock entity registry with test entities."""
    reg = MagicMock()
    
    # Mock entities for wohnbereich
    wohnbereich_entities = [
        MagicMock(entity_id="media_player.sonos_wohnzimmer", original_name="Sonos Wohnzimmer", entity_id.split=".")[0] == "media_player"),
        MagicMock(entity_id="light.wohnzimmer", original_name="Wohnzimmer Licht"),
        MagicMock(entity_id="binary_sensor.motion_wohnzimmer", original_name="Motion Wohnzimmer"),
    ]
    
    # Mock entities for schlafzimmer
    schlafzimmer_entities = [
        MagicMock(entity_id="media_player.sonos_schlafzimmer", original_name="Sonos Schlafzimmer"),
        MagicMock(entity_id="light.schlafzimmer", original_name="Schlafzimmer Licht"),
        MagicMock(entity_id="binary_sensor.motion_schlafzimmer", original_name="Motion Schlafzimmer"),
    ]
    
    def async_entries_for_area(reg_mock, area_id):
        if area_id == "wohnbereich":
            return wohnbereich_entities
        elif area_id == "schlafzimmer":
            return schlafzimmer_entities
        return []
    
    reg.async_entries_for_area = async_entries_for_area
    return reg


class TestZoneConfig:
    """Test ZoneConfig dataclass."""
    
    def test_create_zone_config(self):
        """Test creating a zone configuration."""
        zone = ZoneConfig(
            zone_id="test_zone",
            zone_name="Test Zone",
            area_id="area_123",
        )
        
        assert zone.zone_id == "test_zone"
        assert zone.zone_name == "Test Zone"
        assert isinstance(zone.sonos, SonosConfig)
        assert isinstance(zone.light, LightConfig)
        assert isinstance(zone.presence, PresenceConfig)
        assert isinstance(zone.alarm, AlarmConfig)
        assert isinstance(zone.mood, MoodConfig)
    
    def test_zone_with_sonos_config(self):
        """Test zone with Sonos configuration."""
        zone = ZoneConfig(
            zone_id="wohnbereich",
            sonos=SonosConfig(
                room_name="Wohnzimmer",
                favorite="Morning Playlist",
                volume_default=35,
            ),
        )
        
        assert zone.sonos.room_name == "Wohnzimmer"
        assert zone.sonos.favorite == "Morning Playlist"
        assert zone.sonos.volume_default == 35


class TestCrossModuleConfig:
    """Test CrossModuleConfig class."""
    
    @pytest.mark.asyncio
    async def test_load_empty_storage(self, mock_hass):
        """Test loading when no storage exists."""
        with patch('homeassistant.helpers.storage.Store') as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.async_load = AsyncMock(return_value=None)
            mock_store.return_value = mock_store_instance
            
            config = CrossModuleConfig(mock_hass)
            await config.load()
            
            assert config._loaded is True
            assert isinstance(config._zones, dict)
    
    @pytest.mark.asyncio
    async def test_load_from_storage(self, mock_hass):
        """Test loading from persisted storage."""
        storage_data = {
            "zones": [
                {
                    "zone_id": "test_zone",
                    "zone_name": "Test Zone",
                    "sonos": {"room_name": "Test Room"},
                    "light": {"entities": ["light.test"]},
                    "presence": {"motion_entities": []},
                    "alarm": {"enabled": True},
                    "mood": {"enabled": False},
                }
            ],
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.async_load = AsyncMock(return_value=storage_data)
            mock_store.return_value = mock_store_instance
            
            config = CrossModuleConfig(mock_hass)
            await config.load()
            
            assert len(config._zones) == 1
            assert "test_zone" in config._zones
            assert config._zones["test_zone"].sonos.room_name == "Test Room"
    
    def test_get_zone(self, mock_hass):
        """Test getting a zone by ID."""
        config = CrossModuleConfig(mock_hass)
        zone = ZoneConfig(zone_id="test", zone_name="Test")
        config._zones["test"] = zone
        
        result = config.get_zone("test")
        assert result == zone
        
        result = config.get_zone("nonexistent")
        assert result is None
    
    def test_get_all_zones(self, mock_hass):
        """Test getting all zones."""
        config = CrossModuleConfig(mock_hass)
        config._zones = {
            "zone1": ZoneConfig(zone_id="zone1"),
            "zone2": ZoneConfig(zone_id="zone2"),
        }
        
        zones = config.get_all_zones()
        assert len(zones) == 2
    
    def test_set_zone(self, mock_hass):
        """Test setting/updating a zone."""
        config = CrossModuleConfig(mock_hass)
        zone = ZoneConfig(zone_id="test", zone_name="Test")
        
        config.set_zone(zone)
        
        assert "test" in config._zones
        assert config._zones["test"].zone_name == "Test"
        assert config._zones["test"].updated_at is not None
    
    def test_remove_zone(self, mock_hass):
        """Test removing a zone."""
        config = CrossModuleConfig(mock_hass)
        config._zones["test"] = ZoneConfig(zone_id="test")
        
        result = config.remove_zone("test")
        assert result is True
        assert "test" not in config._zones
        
        result = config.remove_zone("nonexistent")
        assert result is False


class TestConflictDetection:
    """Test conflict detection functionality."""
    
    @pytest.mark.asyncio
    async def test_sonos_room_conflict(self, mock_hass):
        """Test detection of Sonos room mapping conflicts."""
        config = CrossModuleConfig(mock_hass)
        
        # Two zones with same Sonos room
        config._zones = {
            "zone1": ZoneConfig(
                zone_id="zone1",
                sonos=SonosConfig(room_name="Living Room"),
            ),
            "zone2": ZoneConfig(
                zone_id="zone2",
                sonos=SonosConfig(room_name="Living Room"),
            ),
        }
        
        await config._detect_conflicts()
        
        sonos_conflicts = [
            c for c in config._conflicts
            if c.conflict_id.startswith("sonos_room")
        ]
        assert len(sonos_conflicts) == 1
        assert sonos_conflicts[0].severity == "warning"
        assert "zone1" in sonos_conflicts[0].affected_entities
        assert "zone2" in sonos_conflicts[0].affected_entities
    
    @pytest.mark.asyncio
    async def test_wecker_without_sonos(self, mock_hass):
        """Test detection of alarm without Sonos config."""
        config = CrossModuleConfig(mock_hass)
        
        config._zones = {
            "zone1": ZoneConfig(
                zone_id="zone1",
                alarm=AlarmConfig(enabled=True),
                sonos=SonosConfig(room_name=""),
            ),
        }
        
        await config._detect_conflicts()
        
        wecker_conflicts = [
            c for c in config._conflicts
            if c.conflict_id.startswith("wecker_no_sonos")
        ]
        assert len(wecker_conflicts) == 1
        assert wecker_conflicts[0].severity == "warning"
    
    @pytest.mark.asyncio
    async def test_mood_without_motion(self, mock_hass):
        """Test detection of mood inference without motion sensors."""
        config = CrossModuleConfig(mock_hass)
        
        config._zones = {
            "zone1": ZoneConfig(
                zone_id="zone1",
                mood=MoodConfig(enabled=True),
                presence=PresenceConfig(motion_entities=[]),
            ),
        }
        
        await config._detect_conflicts()
        
        mood_conflicts = [
            c for c in config._conflicts
            if c.conflict_id.startswith("mood_no_motion")
        ]
        assert len(mood_conflicts) == 1
        assert mood_conflicts[0].severity == "warning"
    
    def test_get_conflicts_for_zone(self, mock_hass):
        """Test getting conflicts for a specific zone."""
        config = CrossModuleConfig(mock_hass)
        
        config._conflicts = [
            Conflict(
                conflict_id="test_1",
                severity="warning",
                modules=["sonos"],
                description="Test conflict 1",
                affected_entities=["zone1", "zone2"],
            ),
            Conflict(
                conflict_id="test_2",
                severity="info",
                modules=["mood"],
                description="Test conflict 2",
                affected_entities=["zone1"],
            ),
        ]
        
        conflicts = config.get_conflicts_for_zone("zone1")
        assert len(conflicts) == 2
        
        conflicts = config.get_conflicts_for_zone("zone2")
        assert len(conflicts) == 1


class TestSmartDefaults:
    """Test smart defaults application."""
    
    def test_enable_mood_with_motion_sensors(self, mock_hass):
        """Test that mood is enabled when motion sensors exist."""
        config = CrossModuleConfig(mock_hass)
        
        zone = ZoneConfig(
            zone_id="test",
            mood=MoodConfig(enabled=False),
            presence=PresenceConfig(motion_entities=["binary_sensor.motion"]),
            defaults_applied=False,
        )
        config._zones["test"] = zone
        
        config._apply_smart_defaults()
        
        assert config._zones["test"].mood.enabled is True
        assert config._zones["test"].defaults_applied is True
    
    def test_enable_alarm_with_sonos(self, mock_hass):
        """Test that alarm is enabled when Sonos room exists."""
        config = CrossModuleConfig(mock_hass)
        
        zone = ZoneConfig(
            zone_id="test",
            alarm=AlarmConfig(enabled=False),
            sonos=SonosConfig(room_name="Bedroom"),
            defaults_applied=False,
        )
        config._zones["test"] = zone
        
        config._apply_smart_defaults()
        
        assert config._zones["test"].alarm.enabled is True


class TestIntegrationHelpers:
    """Test integration helper methods."""
    
    def test_get_sonos_room_for_zone(self, mock_hass):
        """Test getting Sonos room for zone."""
        config = CrossModuleConfig(mock_hass)
        config._zones = {
            "test": ZoneConfig(
                zone_id="test",
                sonos=SonosConfig(room_name="Test Room"),
            ),
        }
        
        room = config.get_sonos_room_for_zone("test")
        assert room == "Test Room"
        
        room = config.get_sonos_room_for_zone("nonexistent")
        assert room is None
    
    def test_get_light_entities_for_zone(self, mock_hass):
        """Test getting light entities for zone."""
        config = CrossModuleConfig(mock_hass)
        config._zones = {
            "test": ZoneConfig(
                zone_id="test",
                light=LightConfig(entities=["light.one", "light.two"]),
            ),
        }
        
        entities = config.get_light_entities_for_zone("test")
        assert entities == ["light.one", "light.two"]
    
    def test_get_motion_entities_for_zone(self, mock_hass):
        """Test getting motion entities for zone."""
        config = CrossModuleConfig(mock_hass)
        config._zones = {
            "test": ZoneConfig(
                zone_id="test",
                presence=PresenceConfig(motion_entities=["binary_sensor.motion"]),
            ),
        }
        
        entities = config.get_motion_entities_for_zone("test")
        assert entities == ["binary_sensor.motion"]


class TestPersistence:
    """Test persistence functionality."""
    
    def test_to_data(self, mock_hass):
        """Test converting config to persistable data."""
        config = CrossModuleConfig(mock_hass)
        config._zones = {
            "test": ZoneConfig(
                zone_id="test",
                zone_name="Test Zone",
                sonos=SonosConfig(room_name="Test Room"),
                light=LightConfig(entities=["light.test"]),
            ),
        }
        
        data = config._to_data()
        
        assert "zones" in data
        assert len(data["zones"]) == 1
        assert data["zones"][0]["zone_id"] == "test"
        assert data["zones"][0]["sonos"]["room_name"] == "Test Room"
        assert "updated" in data
    
    def test_zone_from_data(self, mock_hass):
        """Test creating ZoneConfig from data."""
        config = CrossModuleConfig(mock_hass)
        
        data = {
            "zone_id": "test",
            "zone_name": "Test Zone",
            "sonos": {"room_name": "Test Room"},
            "light": {"entities": ["light.test"]},
            "presence": {"motion_entities": []},
            "alarm": {"enabled": True},
            "mood": {"enabled": False},
        }
        
        zone = config._zone_from_data(data)
        
        assert zone is not None
        assert zone.zone_id == "test"
        assert zone.sonos.room_name == "Test Room"
        assert zone.light.entities == ["light.test"]
