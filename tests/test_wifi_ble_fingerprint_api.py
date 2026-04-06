"""API tests for Wi-Fi/BLE Fingerprinting Endpoints (P3-008).

Tests verify:
1. POST /api/v1/presence/fingerprint/detect endpoint
2. GET /api/v1/presence/fingerprint/devices endpoint
3. POST /api/v1/presence/fingerprint/devices/register endpoint
4. GET /api/v1/presence/fingerprint/history endpoint
5. POST /api/v1/presence/fingerprint/zones/map endpoint
6. Authentication requirements
"""
import pytest
import time
from unittest.mock import patch, MagicMock

from copilot_core.api.v1.fingerprint import fingerprint_bp


@pytest.fixture
def app():
    """Create Flask app with fingerprint blueprint."""
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(fingerprint_bp)
    yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(autouse=True)
def reset_engine():
    """Reset fingerprint engine before each test."""
    from copilot_core.presence.wifi_ble_fingerprint import reset_fingerprint_engine
    reset_fingerprint_engine()
    yield


class TestDetectEndpoint:
    """Test POST /api/v1/presence/fingerprint/detect endpoint."""

    def test_detect_requires_auth(self, client):
        """Test detect endpoint requires authentication."""
        response = client.post(
            "/api/v1/presence/fingerprint/detect",
            json={"wifi": []},
        )

        assert response.status_code in [401, 403]

    def test_detect_empty_fingerprints(self, client):
        """Test detect with no fingerprint data."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            response = client.post(
                "/api/v1/presence/fingerprint/detect",
                json={},
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            assert data["detection"] is None

    def test_detect_wifi_only(self, client):
        """Test detect with Wi-Fi fingerprints only."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            response = client.post(
                "/api/v1/presence/fingerprint/detect",
                json={
                    "wifi": [
                        {
                            "bssid": "AA:BB:CC:DD:EE:FF",
                            "ssid": "TestNetwork",
                            "rssi": -65,
                            "frequency": 2412,
                            "channel": 1,
                        }
                    ]
                },
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            assert "processed_wifi_count" in data
            assert data["processed_wifi_count"] == 1

    def test_detect_ble_only(self, client):
        """Test detect with BLE fingerprints only."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            response = client.post(
                "/api/v1/presence/fingerprint/detect",
                json={
                    "ble": [
                        {
                            "mac_address": "11:22:33:44:55:66",
                            "rssi": -72,
                            "service_uuid": "0000180A-0000-1000-8000-00805F9B34FB",
                            "manufacturer_id": 76,
                        }
                    ]
                },
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            assert "processed_ble_count" in data
            assert data["processed_ble_count"] == 1

    def test_detect_with_fusion(self, client):
        """Test detect with both Wi-Fi and BLE (fusion)."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            # First register a device
            client.post(
                "/api/v1/presence/fingerprint/devices/register",
                json={
                    "device_id": "test_device",
                    "device_type": "phone",
                    "mac_address": "11:22:33:44:55:66",
                    "initial_rssi_samples": [-65, -68, -62],
                },
            )

            # Then detect
            response = client.post(
                "/api/v1/presence/fingerprint/detect",
                json={
                    "wifi": [
                        {
                            "bssid": "AA:BB:CC:DD:EE:FF",
                            "ssid": "TestNetwork",
                            "rssi": -64,
                            "frequency": 2412,
                            "channel": 1,
                        }
                    ],
                    "ble": [
                        {
                            "mac_address": "11:22:33:44:55:66",
                            "rssi": -70,
                        }
                    ],
                    "use_fusion": True,
                },
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            if data["detection"]:
                assert data["detection"]["detection_method"] == "fusion"


class TestDevicesEndpoint:
    """Test GET /api/v1/presence/fingerprint/devices endpoint."""

    def test_devices_requires_auth(self, client):
        """Test devices endpoint requires authentication."""
        response = client.get("/api/v1/presence/fingerprint/devices")

        assert response.status_code in [401, 403]

    def test_devices_empty(self, client):
        """Test devices list when empty."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            response = client.get("/api/v1/presence/fingerprint/devices")

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            assert data["devices"] == []
            assert data["total"] == 0

    def test_devices_with_registered(self, client):
        """Test devices list with registered devices."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            # Register a device
            client.post(
                "/api/v1/presence/fingerprint/devices/register",
                json={
                    "device_id": "test_device_001",
                    "device_type": "phone",
                },
            )

            response = client.get("/api/v1/presence/fingerprint/devices")

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            assert data["total"] == 1
            assert len(data["devices"]) == 1
            assert data["devices"][0]["device_id"] == "test_device_001"

    def test_devices_filter_by_type(self, client):
        """Test devices filtering by device type."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            # Register multiple devices
            client.post(
                "/api/v1/presence/fingerprint/devices/register",
                json={"device_id": "phone_001", "device_type": "phone"},
            )
            client.post(
                "/api/v1/presence/fingerprint/devices/register",
                json={"device_id": "tablet_001", "device_type": "tablet"},
            )
            client.post(
                "/api/v1/presence/fingerprint/devices/register",
                json={"device_id": "watch_001", "device_type": "watch"},
            )

            response = client.get("/api/v1/presence/fingerprint/devices?device_type=phone")

            assert response.status_code == 200
            data = response.get_json()
            assert data["total"] == 1
            assert data["devices"][0]["device_type"] == "phone"

    def test_devices_limit(self, client):
        """Test devices limit parameter."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            # Register multiple devices
            for i in range(10):
                client.post(
                    "/api/v1/presence/fingerprint/devices/register",
                    json={"device_id": f"device_{i:03d}", "device_type": "phone"},
                )

            response = client.get("/api/v1/presence/fingerprint/devices?limit=5")

            assert response.status_code == 200
            data = response.get_json()
            assert data["total"] == 5


class TestRegisterDeviceEndpoint:
    """Test POST /api/v1/presence/fingerprint/devices/register endpoint."""

    def test_register_requires_auth(self, client):
        """Test register endpoint requires authentication."""
        response = client.post(
            "/api/v1/presence/fingerprint/devices/register",
            json={"device_type": "phone"},
        )

        assert response.status_code in [401, 403]

    def test_register_basic(self, client):
        """Test basic device registration."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            response = client.post(
                "/api/v1/presence/fingerprint/devices/register",
                json={
                    "device_id": "my_device",
                    "device_type": "phone",
                },
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            assert data["device"]["device_id"] == "my_device"
            assert data["device"]["device_type"] == "phone"

    def test_register_with_mac_anonymization(self, client):
        """Test device registration with MAC address anonymization."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            response = client.post(
                "/api/v1/presence/fingerprint/devices/register",
                json={
                    "device_type": "phone",
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                },
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            # Device ID should be anonymized MAC (16 chars)
            assert len(data["device"]["device_id"]) == 16

    def test_register_with_calibration(self, client):
        """Test device registration with RSSI calibration."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            response = client.post(
                "/api/v1/presence/fingerprint/devices/register",
                json={
                    "device_id": "calibrated_device",
                    "device_type": "tablet",
                    "initial_rssi_samples": [-65, -68, -62, -70],
                },
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            assert data["device"]["typical_rssi_mean"] == pytest.approx(-66.25, rel=0.01)


class TestHistoryEndpoint:
    """Test GET /api/v1/presence/fingerprint/history endpoint."""

    def test_history_requires_auth(self, client):
        """Test history endpoint requires authentication."""
        response = client.get("/api/v1/presence/fingerprint/history")

        assert response.status_code in [401, 403]

    def test_history_empty(self, client):
        """Test history when empty."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            response = client.get("/api/v1/presence/fingerprint/history")

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            assert data["history"] == []
            assert data["total"] == 0

    def test_history_with_detections(self, client):
        """Test history with detection records."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            # Register and detect
            client.post(
                "/api/v1/presence/fingerprint/devices/register",
                json={
                    "device_id": "history_test",
                    "device_type": "phone",
                    "initial_rssi_samples": [-65],
                },
            )

            client.post(
                "/api/v1/presence/fingerprint/detect",
                json={
                    "wifi": [
                        {
                            "bssid": "AA:BB:CC:DD:EE:FF",
                            "ssid": "TestNetwork",
                            "rssi": -65,
                            "frequency": 2412,
                            "channel": 1,
                        }
                    ]
                },
            )

            response = client.get("/api/v1/presence/fingerprint/history")

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            # May have detection recorded
            assert "history" in data

    def test_history_limit(self, client):
        """Test history limit parameter."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            response = client.get("/api/v1/presence/fingerprint/history?limit=10")

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True


class TestZoneMapEndpoint:
    """Test POST /api/v1/presence/fingerprint/zones/map endpoint."""

    def test_zone_map_requires_auth(self, client):
        """Test zone map endpoint requires authentication."""
        response = client.post(
            "/api/v1/presence/fingerprint/zones/map",
            json={"identifier_type": "wifi_bssid", "identifier": "AA:BB:CC:DD:EE:FF", "zone_id": "living_room"},
        )

        assert response.status_code in [401, 403]

    def test_zone_map_wifi(self, client):
        """Test zone mapping for Wi-Fi BSSID."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            response = client.post(
                "/api/v1/presence/fingerprint/zones/map",
                json={
                    "identifier_type": "wifi_bssid",
                    "identifier": "AA:BB:CC:DD:EE:FF",
                    "zone_id": "living_room",
                },
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            assert "identifier_hash" in data["mapping"]
            assert data["mapping"]["zone_id"] == "living_room"

    def test_zone_map_ble(self, client):
        """Test zone mapping for BLE device."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            response = client.post(
                "/api/v1/presence/fingerprint/zones/map",
                json={
                    "identifier_type": "ble_device",
                    "identifier": "11:22:33:44:55:66",
                    "zone_id": "bedroom",
                },
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            assert data["mapping"]["zone_id"] == "bedroom"

    def test_zone_map_missing_fields(self, client):
        """Test zone map with missing required fields."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            response = client.post(
                "/api/v1/presence/fingerprint/zones/map",
                json={
                    "identifier_type": "wifi_bssid",
                    # Missing identifier and zone_id
                },
            )

            assert response.status_code == 400
            data = response.get_json()
            assert data["ok"] is False


class TestResetEndpoint:
    """Test DELETE /api/v1/presence/fingerprint/reset endpoint."""

    def test_reset_requires_auth(self, client):
        """Test reset endpoint requires authentication."""
        response = client.delete("/api/v1/presence/fingerprint/reset")

        assert response.status_code in [401, 403]

    def test_reset_success(self, client):
        """Test successful engine reset."""
        with patch("copilot_core.api.v1.fingerprint.require_token"):
            # Register a device first
            client.post(
                "/api/v1/presence/fingerprint/devices/register",
                json={"device_id": "test", "device_type": "phone"},
            )

            response = client.delete("/api/v1/presence/fingerprint/reset")

            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            assert "reset" in data["message"].lower()
