"""Tests for HomeAssistant Client."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from copilot_core.homeassistant.client import (
    HomeAssistantClient,
    HAConnectionConfig,
    HAConnectionStatus,
)


class TestHAConnectionConfig:
    """Test HAConnectionConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = HAConnectionConfig()
        
        assert config.base_url == "http://homeassistant.local:8123"
        assert config.access_token == ""
        assert config.timeout_seconds == 5.0
        assert config.verify_ssl is True
        assert config.retry_count == 3
        assert config.retry_delay_seconds == 1.0
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = HAConnectionConfig(
            base_url="http://custom.local:8123",
            access_token="test-token",
            timeout_seconds=10.0,
            verify_ssl=False,
        )
        
        assert config.base_url == "http://custom.local:8123"
        assert config.access_token == "test-token"
        assert config.timeout_seconds == 10.0
        assert config.verify_ssl is False


class TestHAConnectionStatus:
    """Test HAConnectionStatus dataclass."""
    
    def test_default_status(self):
        """Test default status values."""
        status = HAConnectionStatus()
        
        assert status.connected is False
        assert status.base_url == ""
        assert status.last_error is None
        assert status.last_success is None
        assert status.response_time_ms is None
    
    def test_connected_status(self):
        """Test connected status."""
        status = HAConnectionStatus(
            connected=True,
            base_url="http://test.local:8123",
            last_success=1234567890.0,
            response_time_ms=42.5
        )
        
        assert status.connected is True
        assert status.base_url == "http://test.local:8123"
        assert status.last_success == 1234567890.0
        assert status.response_time_ms == 42.5


class TestHomeAssistantClient:
    """Test HomeAssistantClient."""
    
    def test_client_initialization(self):
        """Test client initialization."""
        config = HAConnectionConfig(
            base_url="http://test.local:8123",
            access_token="test-token"
        )
        client = HomeAssistantClient(config)
        
        assert client.config.base_url == "http://test.local:8123"
        assert client.config.access_token == "test-token"
        assert client._session is None
    
    def test_client_default_config(self):
        """Test client with default config."""
        client = HomeAssistantClient()
        
        assert client.config.base_url == "http://homeassistant.local:8123"
        assert client.config.access_token == ""
    
    @pytest.mark.asyncio
    async def test_close_without_session(self):
        """Test closing client without session."""
        client = HomeAssistantClient()
        
        # Should not raise
        await client.close()
    
    def test_status_property(self):
        """Test status property."""
        client = HomeAssistantClient()
        status = client.status
        
        assert isinstance(status, HAConnectionStatus)
        assert status.connected is False


class TestEntityMapper:
    """Test EntityMapper."""
    
    def test_mapper_initialization(self):
        """Test mapper initialization."""
        from copilot_core.homeassistant import EntityMapper
        
        mapper = EntityMapper()
        assert mapper._area_registry == {}
        assert mapper._entity_mappings == {}
    
    def test_update_area_registry(self):
        """Test updating area registry."""
        from copilot_core.homeassistant import EntityMapper
        
        mapper = EntityMapper()
        areas = [
            {"area_id": "living_room", "name": "Living Room"},
            {"area_id": "kitchen", "name": "Kitchen"},
        ]
        
        mapper.update_area_registry(areas)
        
        assert len(mapper._area_registry) == 2
        assert mapper._area_registry["living_room"]["name"] == "Living Room"
    
    def test_map_light_entity(self):
        """Test mapping a light entity."""
        from copilot_core.homeassistant import EntityMapper, WidgetType
        
        mapper = EntityMapper()
        
        entity_state = {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {
                "friendly_name": "Living Room Light",
                "icon": "mdi:lightbulb",
            }
        }
        
        mapping = mapper.map_entity(entity_state)
        
        assert mapping is not None
        assert mapping.entity_id == "light.living_room"
        assert mapping.widget_type == WidgetType.LIGHT
        assert mapping.name == "Living Room Light"
        assert mapping.state == "on"
        assert mapping.icon == "mdi:lightbulb"
    
    def test_map_sensor_entity(self):
        """Test mapping a sensor entity."""
        from copilot_core.homeassistant import EntityMapper, WidgetType, SensorDeviceClass
        
        mapper = EntityMapper()
        
        entity_state = {
            "entity_id": "sensor.temperature",
            "state": "21.5",
            "attributes": {
                "friendly_name": "Temperature Sensor",
                "device_class": "temperature",
                "unit_of_measurement": "°C",
            }
        }
        
        mapping = mapper.map_entity(entity_state)
        
        assert mapping is not None
        assert mapping.entity_id == "sensor.temperature"
        assert mapping.widget_type == WidgetType.SENSOR
        assert mapping.device_class == "temperature"
        assert mapping.unit_of_measurement == "°C"
        assert mapping.icon == "mdi:thermometer"
    
    def test_map_entities_batch(self):
        """Test mapping multiple entities."""
        from copilot_core.homeassistant import EntityMapper
        
        mapper = EntityMapper()
        
        entities = [
            {
                "entity_id": "light.living_room",
                "state": "on",
                "attributes": {"friendly_name": "Living Room Light"}
            },
            {
                "entity_id": "switch.tv",
                "state": "off",
                "attributes": {"friendly_name": "TV Switch"}
            },
        ]
        
        mappings = mapper.map_entities(entities)
        
        assert len(mappings) == 2
        assert mappings[0].entity_id == "light.living_room"
        assert mappings[1].entity_id == "switch.tv"


class TestAutoDiscovery:
    """Test AutoDiscovery."""
    
    def test_discovery_initialization(self):
        """Test discovery initialization."""
        from copilot_core.homeassistant import AutoDiscovery
        
        discovery = AutoDiscovery()
        assert discovery._discovered == []
        assert discovery._active_client is None
    
    def test_get_discovered_empty(self):
        """Test getting discovered instances when empty."""
        from copilot_core.homeassistant import AutoDiscovery
        
        discovery = AutoDiscovery()
        instances = discovery.get_discovered()
        
        assert instances == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
