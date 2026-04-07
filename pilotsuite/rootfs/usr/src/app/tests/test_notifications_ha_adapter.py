"""Tests for HomeAssistant Notify Adapter.

Tests the HANotifyAdapter class and HA integration endpoints.

Test Coverage:
- HANotifyAdapter initialization and configuration
- Device registration and management
- Notification sending with priority/category mapping
- Payload construction for different notify services
- Connection testing and service discovery
- API endpoint integration tests
- Error handling and edge cases

Requires: pytest, unittest.mock
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timezone

# Import adapter components
from copilot_core.notifications.ha_notify_adapter import (
    HANotifyAdapter,
    HADevice,
    get_ha_notify_adapter,
    reset_ha_notify_adapter,
    PRIORITY_MAP,
    CATEGORY_MAP,
    SUPPORTED_NOTIFY_SERVICES,
)


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = Mock()
    hass.services = Mock()
    hass.services.call = Mock()
    hass.services.async_services = Mock(return_value={
        "notify": {
            "mobile_app_iphone": Mock(),
            "mobile_app_android": Mock(),
            "telegram": Mock(),
            "whatsapp": Mock(),
            "pushover": Mock(),
        }
    })
    return hass


@pytest.fixture
def adapter(mock_hass):
    """Create HANotifyAdapter with mock HA instance."""
    reset_ha_notify_adapter()
    adapter = HANotifyAdapter(mock_hass)
    adapter._refresh_notify_services()
    return adapter


@pytest.fixture
def adapter_no_hass():
    """Create HANotifyAdapter without HA instance."""
    reset_ha_notify_adapter()
    return HANotifyAdapter()


# ═══════════════════════════════════════════════════════════════════════════
# Test Priority and Category Mappings
# ═══════════════════════════════════════════════════════════════════════════


class TestPriorityMapping:
    """Test priority mapping constants."""
    
    def test_priority_map_contains_all_levels(self):
        """Test that PRIORITY_MAP contains all priority levels."""
        assert "low" in PRIORITY_MAP
        assert "normal" in PRIORITY_MAP
        assert "high" in PRIORITY_MAP
        assert "urgent" in PRIORITY_MAP
    
    def test_priority_map_has_priority_and_urgency(self):
        """Test that each priority level has priority and urgency."""
        for level, config in PRIORITY_MAP.items():
            assert "priority" in config
            assert "urgency" in config
            assert isinstance(config["priority"], int)
            assert isinstance(config["urgency"], str)
    
    def test_priority_values_are_valid(self):
        """Test that priority values are in valid range."""
        for level, config in PRIORITY_MAP.items():
            assert 0 <= config["priority"] <= 3
    
    def test_category_map_contains_all_types(self):
        """Test that CATEGORY_MAP contains all notification types."""
        assert "mood_change" in CATEGORY_MAP
        assert "alert" in CATEGORY_MAP
        assert "suggestion" in CATEGORY_MAP
        assert "system" in CATEGORY_MAP
        assert "info" in CATEGORY_MAP
        assert "warning" in CATEGORY_MAP


# ═══════════════════════════════════════════════════════════════════════════
# Test HANotifyAdapter Initialization
# ═══════════════════════════════════════════════════════════════════════════


class TestHANotifyAdapterInit:
    """Test HANotifyAdapter initialization."""
    
    def test_init_without_hass(self):
        """Test adapter initialization without HA instance."""
        adapter = HANotifyAdapter()
        assert adapter.hass is None
        assert adapter._devices == {}
        assert adapter._notify_services == []
    
    def test_init_with_hass(self, mock_hass):
        """Test adapter initialization with HA instance."""
        adapter = HANotifyAdapter(mock_hass)
        assert adapter.hass is mock_hass
        assert adapter._devices == {}
    
    def test_set_hass(self, adapter_no_hass, mock_hass):
        """Test setting HA instance after initialization."""
        adapter_no_hass.set_hass(mock_hass)
        assert adapter_no_hass.hass is mock_hass
    
    def test_singleton_pattern(self, mock_hass):
        """Test singleton pattern for adapter."""
        reset_ha_notify_adapter()
        adapter1 = get_ha_notify_adapter(mock_hass)
        adapter2 = get_ha_notify_adapter()
        assert adapter1 is adapter2
    
    def test_singleton_reset(self, mock_hass):
        """Test singleton reset functionality."""
        reset_ha_notify_adapter()
        adapter1 = get_ha_notify_adapter(mock_hass)
        reset_ha_notify_adapter()
        adapter2 = get_ha_notify_adapter()
        assert adapter1 is not adapter2


# ═══════════════════════════════════════════════════════════════════════════
# Test Device Registration
# ═══════════════════════════════════════════════════════════════════════════


class TestDeviceRegistration:
    """Test device registration functionality."""
    
    def test_register_ha_device_success(self, adapter):
        """Test successful device registration."""
        device = adapter.register_ha_device(
            user_id="user123",
            ha_entity_id="notify.mobile_app_iphone",
            device_name="My iPhone",
            device_type="mobile"
        )
        
        assert device is not None
        assert device.user_id == "user123"
        assert device.ha_entity_id == "notify.mobile_app_iphone"
        assert device.device_name == "My iPhone"
        assert device.device_type == "mobile"
        assert device.enabled is True
        assert device.id is not None
    
    def test_register_device_auto_detects_type(self, adapter):
        """Test automatic device type detection from entity_id."""
        # Mobile app
        device1 = adapter.register_ha_device("user1", "notify.mobile_app_iphone")
        assert device1.device_type == "mobile"
        
        # Telegram
        device2 = adapter.register_ha_device("user1", "notify.telegram")
        assert device2.device_type == "telegram"
        
        # WhatsApp
        device3 = adapter.register_ha_device("user1", "notify.whatsapp")
        assert device3.device_type == "whatsapp"
    
    def test_register_device_invalid_entity_id(self, adapter):
        """Test registration with invalid entity_id format."""
        with pytest.raises(ValueError, match="must start with 'notify.'"):
            adapter.register_ha_device("user1", "mobile_app_iphone")
    
    def test_register_device_without_name(self, adapter):
        """Test registration without explicit device name."""
        device = adapter.register_ha_device(
            user_id="user1",
            ha_entity_id="notify.mobile_app_iphone"
        )
        assert device.device_name == "notify.mobile_app_iphone"
    
    def test_get_ha_devices(self, adapter):
        """Test retrieving devices for a user."""
        adapter.register_ha_device("user1", "notify.mobile_app_iphone", "iPhone")
        adapter.register_ha_device("user1", "notify.telegram", "Telegram")
        adapter.register_ha_device("user2", "notify.whatsapp", "WhatsApp")
        
        user1_devices = adapter.get_ha_devices("user1")
        user2_devices = adapter.get_ha_devices("user2")
        user3_devices = adapter.get_ha_devices("user3")
        
        assert len(user1_devices) == 2
        assert len(user2_devices) == 1
        assert len(user3_devices) == 0
    
    def test_get_all_devices(self, adapter):
        """Test retrieving all devices across all users."""
        adapter.register_ha_device("user1", "notify.mobile_app_iphone")
        adapter.register_ha_device("user1", "notify.telegram")
        adapter.register_ha_device("user2", "notify.whatsapp")
        
        all_devices = adapter.get_all_devices()
        assert len(all_devices) == 3
    
    def test_unregister_ha_device(self, adapter):
        """Test device unregistration."""
        device = adapter.register_ha_device("user1", "notify.mobile_app_iphone")
        
        # Should find device
        devices_before = adapter.get_ha_devices("user1")
        assert len(devices_before) == 1
        
        # Unregister
        result = adapter.unregister_ha_device(device.id)
        assert result is True
        
        # Should not find device
        devices_after = adapter.get_ha_devices("user1")
        assert len(devices_after) == 0
    
    def test_unregister_nonexistent_device(self, adapter):
        """Test unregistering a device that doesn't exist."""
        result = adapter.unregister_ha_device("nonexistent_id")
        assert result is False
    
    def test_enable_disable_device(self, adapter):
        """Test enabling and disabling devices."""
        device = adapter.register_ha_device("user1", "notify.mobile_app_iphone")
        
        # Initially enabled
        assert device.enabled is True
        
        # Disable
        result = adapter.disable_device(device.id)
        assert result is True
        assert device.enabled is False
        
        # Enable
        result = adapter.enable_device(device.id)
        assert result is True
        assert device.enabled is True
    
    def test_enable_disable_nonexistent_device(self, adapter):
        """Test enabling/disabling nonexistent device."""
        assert adapter.enable_device("nonexistent") is False
        assert adapter.disable_device("nonexistent") is False


# ═══════════════════════════════════════════════════════════════════════════
# Test Payload Construction
# ═══════════════════════════════════════════════════════════════════════════


class TestPayloadConstruction:
    """Test notification payload construction."""
    
    def test_build_payload_minimal(self, adapter):
        """Test payload with minimal parameters."""
        payload = adapter._build_payload(message="Test message")
        
        assert payload["message"] == "Test message"
        assert "title" not in payload
        assert "data" in payload
        assert payload["data"]["priority"] == 1  # normal
        assert payload["data"]["urgency"] == "normal"
    
    def test_build_payload_with_title(self, adapter):
        """Test payload with title."""
        payload = adapter._build_payload(
            message="Test message",
            title="Test Title"
        )
        
        assert payload["title"] == "Test Title"
        assert payload["message"] == "Test message"
    
    def test_build_payload_priority_mapping(self, adapter):
        """Test priority mapping in payload."""
        # Low priority
        payload_low = adapter._build_payload("msg", priority="low")
        assert payload_low["data"]["priority"] == 0
        assert payload_low["data"]["urgency"] == "low"
        
        # High priority
        payload_high = adapter._build_payload("msg", priority="high")
        assert payload_high["data"]["priority"] == 2
        assert payload_high["data"]["urgency"] == "high"
        
        # Urgent priority
        payload_urgent = adapter._build_payload("msg", priority="urgent")
        assert payload_urgent["data"]["priority"] == 3
        assert payload_urgent["data"]["urgency"] == "emergency"
    
    def test_build_payload_category_mapping(self, adapter):
        """Test category mapping in payload."""
        payload_alert = adapter._build_payload("msg", notification_type="alert")
        assert payload_alert["data"]["category"] == "alert"
        
        payload_mood = adapter._build_payload("msg", notification_type="mood_change")
        assert payload_mood["data"]["category"] == "mood"
        
        payload_info = adapter._build_payload("msg", notification_type="info")
        assert payload_info["data"]["category"] == "info"
    
    def test_build_payload_with_additional_data(self, adapter):
        """Test payload with additional data."""
        extra_data = {"url": "https://example.com", "badge": 5}
        payload = adapter._build_payload(
            message="Test",
            data=extra_data
        )
        
        assert payload["data"]["url"] == "https://example.com"
        assert payload["data"]["badge"] == 5
        # Should still have priority/category
        assert "priority" in payload["data"]
        assert "category" in payload["data"]
    
    def test_build_payload_unknown_priority_defaults_to_normal(self, adapter):
        """Test that unknown priority defaults to normal."""
        payload = adapter._build_payload("msg", priority="unknown_priority")
        assert payload["data"]["priority"] == 1
        assert payload["data"]["urgency"] == "normal"


# ═══════════════════════════════════════════════════════════════════════════
# Test Send Notification
# ═══════════════════════════════════════════════════════════════════════════


class TestSendNotification:
    """Test notification sending functionality."""
    
    def test_send_to_ha_service_success(self, adapter, mock_hass):
        """Test successful notification sending."""
        device = adapter.register_ha_device(
            user_id="user1",
            ha_entity_id="notify.mobile_app_iphone"
        )
        
        result = adapter.send_to_ha_service(
            device_id=device.id,
            message="Test notification",
            priority="high",
            title="Test Title"
        )
        
        assert result is True
        mock_hass.services.call.assert_called_once()
        
        # Verify call arguments
        call_args = mock_hass.services.call.call_args
        assert call_args[0][0] == "notify"
        assert call_args[0][1] == "mobile_app_iphone"
        assert call_args[1]["blocking"] is False
        
        payload = call_args[0][2]
        assert payload["message"] == "Test notification"
        assert payload["title"] == "Test Title"
        assert payload["data"]["priority"] == 2  # high
    
    def test_send_to_ha_service_device_not_found(self, adapter):
        """Test sending to nonexistent device."""
        with pytest.raises(ValueError, match="Device not found"):
            adapter.send_to_ha_service(
                device_id="nonexistent",
                message="Test"
            )
    
    def test_send_to_ha_service_disabled_device(self, adapter, mock_hass):
        """Test sending to disabled device."""
        device = adapter.register_ha_device("user1", "notify.mobile_app_iphone")
        adapter.disable_device(device.id)
        
        result = adapter.send_to_ha_service(device.id, "Test")
        
        assert result is False
        mock_hass.services.call.assert_not_called()
    
    def test_send_to_ha_service_no_hass(self, adapter_no_hass):
        """Test sending without HA instance."""
        device = adapter_no_hass.register_ha_device("user1", "notify.mobile_app_iphone")
        
        with pytest.raises(RuntimeError, match="HomeAssistant instance not configured"):
            adapter_no_hass.send_to_ha_service(device.id, "Test")
    
    def test_send_to_ha_service_unavailable_service(self, adapter, mock_hass):
        """Test sending when notify service is unavailable."""
        # Mock empty services
        mock_hass.services.async_services = Mock(return_value={"notify": {}})
        adapter._refresh_notify_services()
        
        device = adapter.register_ha_device("user1", "notify.mobile_app_iphone")
        result = adapter.send_to_ha_service(device.id, "Test")
        
        assert result is False
    
    def test_send_updates_last_used(self, adapter, mock_hass):
        """Test that sending updates device last_used timestamp."""
        device = adapter.register_ha_device("user1", "notify.mobile_app_iphone")
        assert device.last_used == ""
        
        adapter.send_to_ha_service(device.id, "Test")
        
        assert device.last_used != ""
        # Should be valid ISO format
        datetime.fromisoformat(device.last_used)


# ═══════════════════════════════════════════════════════════════════════════
# Test Connection Testing
# ═══════════════════════════════════════════════════════════════════════════


class TestConnectionTesting:
    """Test connection testing functionality."""
    
    def test_test_ha_connection_success(self, adapter, mock_hass):
        """Test successful connection test."""
        result = adapter.test_ha_connection()
        
        assert result["success"] is True
        assert result["hass_connected"] is True
        assert result["notify_services_available"] is True
        assert result["services_count"] == 5
        assert len(result["services"]) == 5
    
    def test_test_ha_connection_no_hass(self, adapter_no_hass):
        """Test connection test without HA instance."""
        result = adapter_no_hass.test_ha_connection()
        
        assert result["success"] is False
        assert result["hass_connected"] is False
        assert result["error"] == "HomeAssistant instance not configured"
    
    def test_test_ha_connection_no_services(self, adapter, mock_hass):
        """Test connection test with no notify services."""
        mock_hass.services.async_services = Mock(return_value={"notify": {}})
        adapter._refresh_notify_services()
        
        result = adapter.test_ha_connection()
        
        assert result["success"] is True  # HA connected, just no services
        assert result["notify_services_available"] is False
        assert result["services_count"] == 0
    
    def test_get_available_notify_services(self, adapter):
        """Test getting available notify services."""
        services = adapter.get_available_notify_services()
        
        assert len(services) == 5
        assert "mobile_app_iphone" in services
        assert "telegram" in services
        assert "whatsapp" in services
    
    def test_refresh_notify_services(self, adapter, mock_hass):
        """Test service refresh functionality."""
        # Change available services
        mock_hass.services.async_services = Mock(return_value={
            "notify": {
                "pushover": Mock(),
                "email": Mock(),
            }
        })
        
        adapter._refresh_notify_services()
        services = adapter.get_available_notify_services()
        
        assert len(services) == 2
        assert "pushover" in services
        assert "email" in services


# ═══════════════════════════════════════════════════════════════════════════
# Test HADevice Data Class
# ═══════════════════════════════════════════════════════════════════════════


class TestHADevice:
    """Test HADevice data class."""
    
    def test_hadevice_default_values(self):
        """Test HADevice default values."""
        device = HADevice()
        
        assert device.id is not None
        assert device.user_id == ""
        assert device.ha_entity_id == ""
        assert device.device_name == ""
        assert device.device_type == "mobile"
        assert device.enabled is True
        assert device.last_used == ""
    
    def test_hadevice_to_dict(self):
        """Test HADevice to_dict method."""
        device = HADevice(
            user_id="user123",
            ha_entity_id="notify.mobile_app_iphone",
            device_name="My iPhone",
            device_type="mobile"
        )
        
        device_dict = device.to_dict()
        
        assert device_dict["user_id"] == "user123"
        assert device_dict["ha_entity_id"] == "notify.mobile_app_iphone"
        assert device_dict["device_name"] == "My iPhone"
        assert device_dict["device_type"] == "mobile"
        assert device_dict["enabled"] is True
        assert "id" in device_dict
        assert "created_at" in device_dict
    
    def test_hadevice_custom_id(self):
        """Test HADevice with custom values."""
        device = HADevice(
            id="custom_id_123",
            user_id="user456",
            ha_entity_id="notify.telegram_bot",
            device_name="Telegram Bot",
            device_type="telegram",
            enabled=False
        )
        
        assert device.id == "custom_id_123"
        assert device.user_id == "user456"
        assert device.enabled is False


# ═══════════════════════════════════════════════════════════════════════════
# Test Service Name Extraction
# ═══════════════════════════════════════════════════════════════════════════


class TestServiceNameExtraction:
    """Test notify service name extraction."""
    
    def test_extract_service_name_with_prefix(self, adapter):
        """Test extraction from full entity_id."""
        service_name = adapter._get_notify_service_name("notify.mobile_app_iphone")
        assert service_name == "mobile_app_iphone"
    
    def test_extract_service_name_without_prefix(self, adapter):
        """Test extraction when already without prefix."""
        service_name = adapter._get_notify_service_name("mobile_app_iphone")
        assert service_name == "mobile_app_iphone"
    
    def test_is_service_available(self, adapter):
        """Test service availability check."""
        assert adapter._is_service_available("mobile_app_iphone") is True
        assert adapter._is_service_available("nonexistent_service") is False


# ═══════════════════════════════════════════════════════════════════════════
# Integration Tests (Flask API Endpoints)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.skip(reason="Requires full Flask app setup")
class TestHAEndpointsIntegration:
    """Integration tests for HA notify API endpoints."""
    
    def test_register_ha_device_endpoint(self, app_with_notifications):
        """Test POST /api/v1/notifications/ha/register endpoint."""
        with app_with_notifications.test_client() as client:
            response = client.post(
                "/api/v1/notifications/ha/register",
                json={
                    "user_id": "user123",
                    "ha_entity_id": "notify.mobile_app_iphone",
                    "device_name": "Test iPhone"
                },
                headers={"X-Auth-Token": "test_token"}
            )
            
            assert response.status_code == 201
            data = response.get_json()
            assert data["success"] is True
            assert data["data"]["ha_entity_id"] == "notify.mobile_app_iphone"
    
    def test_get_ha_devices_endpoint(self, app_with_notifications):
        """Test GET /api/v1/notifications/ha/devices endpoint."""
        with app_with_notifications.test_client() as client:
            response = client.get(
                "/api/v1/notifications/ha/devices",
                headers={"X-Auth-Token": "test_token"}
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert "devices" in data["data"]
    
    def test_send_ha_notification_endpoint(self, app_with_notifications):
        """Test POST /api/v1/notifications/send/ha endpoint."""
        with app_with_notifications.test_client() as client:
            response = client.post(
                "/api/v1/notifications/send/ha",
                json={
                    "device_id": "test_device",
                    "message": "Test notification",
                    "priority": "high"
                },
                headers={"X-Auth-Token": "test_token"}
            )
            
            # Will fail without registered device, but tests endpoint exists
            assert response.status_code in [200, 400, 500]
    
    def test_test_ha_connection_endpoint(self, app_with_notifications):
        """Test GET /api/v1/notifications/ha/test endpoint."""
        with app_with_notifications.test_client() as client:
            response = client.get(
                "/api/v1/notifications/ha/test",
                headers={"X-Auth-Token": "test_token"}
            )
            
            assert response.status_code in [200, 503]
            data = response.get_json()
            assert "success" in data
            assert "data" in data


# ═══════════════════════════════════════════════════════════════════════════
# Edge Cases and Error Handling
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_register_multiple_devices_same_user(self, adapter):
        """Test registering multiple devices for same user."""
        device1 = adapter.register_ha_device("user1", "notify.mobile_app_iphone", "iPhone")
        device2 = adapter.register_ha_device("user1", "notify.telegram", "Telegram")
        device3 = adapter.register_ha_device("user1", "notify.whatsapp", "WhatsApp")
        
        devices = adapter.get_ha_devices("user1")
        assert len(devices) == 3
        assert device1.id != device2.id != device3.id
    
    def test_send_with_empty_message(self, adapter, mock_hass):
        """Test sending notification with empty message."""
        device = adapter.register_ha_device("user1", "notify.mobile_app_iphone")
        
        # Empty message should still work (HA will handle validation)
        result = adapter.send_to_ha_service(device.id, "")
        assert result is True
    
    def test_send_with_special_characters(self, adapter, mock_hass):
        """Test sending notification with special characters."""
        device = adapter.register_ha_device("user1", "notify.mobile_app_iphone")
        
        message = "Test with special chars: äöü ñ 你好 🎉"
        result = adapter.send_to_ha_service(device.id, message)
        
        assert result is True
        call_args = mock_hass.services.call.call_args
        assert call_args[0][2]["message"] == message
    
    def test_payload_with_none_values(self, adapter):
        """Test payload construction with None values."""
        payload = adapter._build_payload(
            message="Test",
            title=None,
            priority=None,
            data=None
        )
        
        assert payload["message"] == "Test"
        assert "data" in payload  # Should have default data
    
    def test_find_device_across_users(self, adapter):
        """Test finding device across multiple users."""
        device1 = adapter.register_ha_device("user1", "notify.mobile_app_iphone")
        adapter.register_ha_device("user2", "notify.telegram")
        
        found = adapter._find_device(device1.id)
        assert found is device1
        assert found.user_id == "user1"


# ═══════════════════════════════════════════════════════════════════════════
# Test Supported Services Documentation
# ═══════════════════════════════════════════════════════════════════════════


class TestSupportedServices:
    """Test supported services documentation."""
    
    def test_supported_services_contains_mobile_app(self):
        """Test that mobile_app is in supported services."""
        assert "mobile_app" in SUPPORTED_NOTIFY_SERVICES
    
    def test_supported_services_contains_telegram(self):
        """Test that telegram is in supported services."""
        assert "telegram" in SUPPORTED_NOTIFY_SERVICES
    
    def test_supported_services_contains_whatsapp(self):
        """Test that whatsapp is in supported services."""
        assert "whatsapp" in SUPPORTED_NOTIFY_SERVICES
    
    def test_supported_services_has_descriptions(self):
        """Test that all services have descriptions."""
        for service, description in SUPPORTED_NOTIFY_SERVICES.items():
            assert description is not None
            assert len(description) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Run Tests
# ═══════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
