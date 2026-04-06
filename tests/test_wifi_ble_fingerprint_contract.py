"""Contract tests for Wi-Fi/BLE Fingerprinting Presence Detection (P3-008).

Tests verify:
1. WiFiFingerprint and BLEFingerprint data structures
2. MAC address anonymization for privacy
3. Device fingerprint profile registration
4. Presence detection with Wi-Fi, BLE, and fusion
5. Confidence scoring and signal quality
6. API endpoint contracts
"""
import pytest
import time
from datetime import datetime, timezone

from copilot_core.presence.wifi_ble_fingerprint import (
    WiFiFingerprint,
    BLEFingerprint,
    DeviceFingerprintProfile,
    PresenceDetection,
    FingerprintEngine,
    anonymize_mac,
    rssi_to_distance,
    calculate_signal_quality,
    gaussian_kernel,
    RSSI_EXCELLENT,
    RSSI_GOOD,
    RSSI_FAIR,
    RSSI_POOR,
    PRESENCE_CONFIDENCE_THRESHOLD,
    get_fingerprint_engine,
    reset_fingerprint_engine,
)


@pytest.fixture(autouse=True)
def reset_engine():
    """Reset fingerprint engine before each test."""
    reset_fingerprint_engine()
    yield


class TestMACAnonymization:
    """Test MAC address anonymization for privacy."""

    def test_anonymize_mac_format(self):
        """Test MAC anonymization returns correct format."""
        mac = "AA:BB:CC:DD:EE:FF"
        anonymized = anonymize_mac(mac)

        assert len(anonymized) == 16
        assert all(c in "0123456789abcdef" for c in anonymized)

    def test_anonymize_mac_normalized(self):
        """Test MAC normalization (dash vs colon)."""
        mac1 = "AA:BB:CC:DD:EE:FF"
        mac2 = "AA-BB-CC-DD-EE-FF"

        assert anonymize_mac(mac1) == anonymize_mac(mac2)

    def test_anonymize_mac_case_insensitive(self):
        """Test case insensitivity."""
        mac1 = "aa:bb:cc:dd:ee:ff"
        mac2 = "AA:BB:CC:DD:EE:FF"

        assert anonymize_mac(mac1) == anonymize_mac(mac2)

    def test_anonymize_mac_deterministic(self):
        """Test same MAC always produces same hash."""
        mac = "11:22:33:44:55:66"
        hash1 = anonymize_mac(mac)
        hash2 = anonymize_mac(mac)

        assert hash1 == hash2

    def test_anonymize_mac_different_macs(self):
        """Test different MACs produce different hashes."""
        mac1 = "AA:BB:CC:DD:EE:FF"
        mac2 = "AA:BB:CC:DD:EE:FE"

        assert anonymize_mac(mac1) != anonymize_mac(mac2)


class TestRSSIUtilities:
    """Test RSSI utility functions."""

    def test_rssi_to_distance_strong_signal(self):
        """Test distance estimation for strong signal."""
        distance = rssi_to_distance(-40)
        assert 0.1 <= distance <= 2.0

    def test_rssi_to_distance_weak_signal(self):
        """Test distance estimation for weak signal."""
        distance = rssi_to_distance(-85)
        assert distance > 5.0

    def test_rssi_to_distance_bounds(self):
        """Test distance is clamped to reasonable range."""
        very_strong = rssi_to_distance(-10)
        very_weak = rssi_to_distance(-120)

        assert 0.1 <= very_strong <= 50.0
        assert 0.1 <= very_weak <= 50.0

    def test_signal_quality_excellent(self):
        """Test excellent signal quality classification."""
        assert calculate_signal_quality(-45) == "excellent"
        assert calculate_signal_quality(-50) == "excellent"

    def test_signal_quality_good(self):
        """Test good signal quality classification."""
        assert calculate_signal_quality(-55) == "good"
        assert calculate_signal_quality(-60) == "good"

    def test_signal_quality_fair(self):
        """Test fair signal quality classification."""
        assert calculate_signal_quality(-65) == "fair"
        assert calculate_signal_quality(-70) == "fair"

    def test_signal_quality_poor(self):
        """Test poor signal quality classification."""
        assert calculate_signal_quality(-75) == "poor"
        assert calculate_signal_quality(-80) == "poor"

    def test_signal_quality_unusable(self):
        """Test unusable signal quality classification."""
        assert calculate_signal_quality(-85) == "unusable"
        assert calculate_signal_quality(-95) == "unusable"

    def test_gaussian_kernel_center(self):
        """Test Gaussian kernel at mean."""
        value = gaussian_kernel(0.0, 0.0, 1.0)
        assert value == 1.0

    def test_gaussian_kernel_one_std(self):
        """Test Gaussian kernel at one standard deviation."""
        value = gaussian_kernel(1.0, 0.0, 1.0)
        assert 0.5 < value < 0.7


class TestWiFiFingerprint:
    """Test Wi-Fi fingerprint data structure."""

    def test_wifi_fingerprint_creation(self):
        """Test WiFiFingerprint creation."""
        fp = WiFiFingerprint(
            bssid_hash="a1b2c3d4e5f6g7h8",
            ssid_hash="network12345678",
            rssi=-65,
            frequency=2412,
            channel=1,
            timestamp=time.time(),
        )

        assert fp.bssid_hash == "a1b2c3d4e5f6g7h8"
        assert fp.rssi == -65
        assert fp.frequency == 2412
        assert fp.channel == 1
        assert fp.noise is None

    def test_wifi_fingerprint_with_noise(self):
        """Test WiFiFingerprint with noise floor."""
        fp = WiFiFingerprint(
            bssid_hash="a1b2c3d4e5f6g7h8",
            ssid_hash="network12345678",
            rssi=-65,
            frequency=5180,
            channel=36,
            timestamp=time.time(),
            noise=-92,
        )

        assert fp.noise == -92


class TestBLEFingerprint:
    """Test BLE fingerprint data structure."""

    def test_ble_fingerprint_creation(self):
        """Test BLEFingerprint creation."""
        fp = BLEFingerprint(
            device_hash="b2c3d4e5f6g7h8i9",
            rssi=-72,
            service_uuid="0000180A-0000-1000-8000-00805F9B34FB",
            manufacturer_id=76,
            tx_power=-59,
            timestamp=time.time(),
        )

        assert fp.device_hash == "b2c3d4e5f6g7h8i9"
        assert fp.rssi == -72
        assert fp.service_uuid == "0000180A-0000-1000-8000-00805F9B34FB"
        assert fp.manufacturer_id == 76
        assert fp.tx_power == -59


class TestFingerprintEngine:
    """Test FingerprintEngine core functionality."""

    def test_engine_initialization(self):
        """Test engine initializes with empty state."""
        engine = FingerprintEngine()

        assert len(engine.get_device_profiles()) == 0
        assert len(engine.get_detection_history()) == 0

    def test_register_device_basic(self):
        """Test basic device registration."""
        engine = FingerprintEngine()

        profile = engine.register_device(
            device_id="test_device_001",
            device_type="phone",
        )

        assert profile.device_id == "test_device_001"
        assert profile.device_type == "phone"
        assert profile.confidence_score == 0.0

    def test_register_device_with_calibration(self):
        """Test device registration with RSSI calibration."""
        engine = FingerprintEngine()

        profile = engine.register_device(
            device_id="test_device_002",
            device_type="tablet",
            initial_wifi_rssi=[-65, -68, -62, -70, -66],
        )

        assert profile.typical_rssi_mean == pytest.approx(-66.2, rel=0.01)
        assert profile.typical_rssi_std > 0

    def test_process_wifi_fingerprint(self):
        """Test Wi-Fi fingerprint processing."""
        engine = FingerprintEngine()

        fp = engine.process_wifi_fingerprint(
            bssid="AA:BB:CC:DD:EE:FF",
            ssid="TestNetwork",
            rssi=-65,
            frequency=2412,
            channel=1,
        )

        assert len(fp.bssid_hash) == 16
        assert len(fp.ssid_hash) == 16
        assert fp.rssi == -65

    def test_process_ble_fingerprint(self):
        """Test BLE fingerprint processing."""
        engine = FingerprintEngine()

        fp = engine.process_ble_fingerprint(
            mac_address="11:22:33:44:55:66",
            rssi=-72,
            service_uuid="0000180A-0000-1000-8000-00805F9B34FB",
            manufacturer_id=76,
        )

        assert len(fp.device_hash) == 16
        assert fp.rssi == -72
        assert fp.service_uuid == "0000180A-0000-1000-8000-00805F9B34FB"

    def test_detect_presence_no_data(self):
        """Test presence detection with no fingerprint data."""
        engine = FingerprintEngine()

        detection = engine.detect_presence()

        assert detection is None

    def test_detect_presence_with_registered_device(self):
        """Test presence detection for registered device."""
        engine = FingerprintEngine()

        # Register device with calibration
        engine.register_device(
            device_id="known_device",
            device_type="phone",
            initial_wifi_rssi=[-65, -68, -62],
        )

        # Submit matching fingerprint
        engine.process_wifi_fingerprint(
            bssid="AA:BB:CC:DD:EE:FF",
            ssid="TestNetwork",
            rssi=-65,
            frequency=2412,
            channel=1,
        )

        detection = engine.detect_presence()

        assert detection is not None
        assert detection.device_id == "known_device"
        assert detection.device_type == "phone"
        assert detection.wifi_rssi is not None

    def test_detect_presence_fusion(self):
        """Test multi-sensor fusion detection."""
        engine = FingerprintEngine()

        # Register device
        engine.register_device(
            device_id="fusion_device",
            device_type="phone",
            initial_wifi_rssi=[-65, -68],
        )

        # Submit both Wi-Fi and BLE fingerprints
        engine.process_wifi_fingerprint(
            bssid="AA:BB:CC:DD:EE:FF",
            ssid="TestNetwork",
            rssi=-64,
            frequency=2412,
            channel=1,
        )

        engine.process_ble_fingerprint(
            mac_address="11:22:33:44:55:66",
            rssi=-70,
        )

        detection = engine.detect_presence(use_fusion=True)

        assert detection is not None
        assert detection.detection_method == "fusion"
        assert detection.wifi_rssi is not None
        assert detection.ble_rssi is not None

    def test_detect_presence_confidence_threshold(self):
        """Test presence detection respects confidence threshold."""
        engine = FingerprintEngine()

        # Register device
        engine.register_device(
            device_id="threshold_device",
            device_type="watch",
            initial_wifi_rssi=[-65, -68, -62, -70],
        )

        # Submit strong fingerprint
        for _ in range(5):
            engine.process_wifi_fingerprint(
                bssid="AA:BB:CC:DD:EE:FF",
                ssid="TestNetwork",
                rssi=-65,
                frequency=2412,
                channel=1,
            )

        detection = engine.detect_presence()

        assert detection is not None
        assert detection.is_present == (detection.confidence >= PRESENCE_CONFIDENCE_THRESHOLD)

    def test_zone_inference_strong_signal(self):
        """Test zone inference from strong signal."""
        engine = FingerprintEngine()

        engine.register_device(
            device_id="zone_device",
            device_type="phone",
            initial_wifi_rssi=[-65],
        )

        # Submit very strong signal
        engine.process_wifi_fingerprint(
            bssid="AA:BB:CC:DD:EE:FF",
            ssid="TestNetwork",
            rssi=-45,
            frequency=2412,
            channel=1,
        )

        detection = engine.detect_presence()

        assert detection is not None
        assert detection.location_zone in ["near_ap", "same_room", "building"]

    def test_detection_history_tracking(self):
        """Test detection history is recorded."""
        engine = FingerprintEngine()

        engine.register_device(
            device_id="history_device",
            device_type="phone",
            initial_wifi_rssi=[-65],
        )

        # Generate multiple detections
        for i in range(5):
            engine.process_wifi_fingerprint(
                bssid="AA:BB:CC:DD:EE:FF",
                ssid="TestNetwork",
                rssi=-65 - i,
                frequency=2412,
                channel=1,
            )
            engine.detect_presence()

        history = engine.get_detection_history()

        assert len(history) >= 1

    def test_zone_mapping(self):
        """Test zone mapping for identifiers."""
        engine = FingerprintEngine()

        engine.set_zone_mapping("test_hash_123", "living_room")

        # Zone mapping is stored internally
        assert "test_hash_123" in engine._zone_mapping
        assert engine._zone_mapping["test_hash_123"] == "living_room"


class TestPresenceDetection:
    """Test PresenceDetection result structure."""

    def test_detection_present(self):
        """Test PresenceDetection for present device."""
        detection = PresenceDetection(
            device_id="test_device",
            device_type="phone",
            is_present=True,
            confidence=0.85,
            location_zone="living_room",
            detection_method="fusion",
            wifi_rssi=-62.5,
            ble_rssi=-70.0,
        )

        assert detection.is_present is True
        assert detection.confidence == 0.85
        assert detection.detection_method == "fusion"

    def test_detection_absent(self):
        """Test PresenceDetection for absent device."""
        detection = PresenceDetection(
            device_id="test_device",
            device_type="phone",
            is_present=False,
            confidence=0.35,
            location_zone=None,
            detection_method="wifi",
            wifi_rssi=-85.0,
        )

        assert detection.is_present is False
        assert detection.confidence == 0.35


class TestGlobalEngine:
    """Test global engine instance management."""

    def test_get_fingerprint_engine_singleton(self):
        """Test get_fingerprint_engine returns singleton."""
        engine1 = get_fingerprint_engine()
        engine2 = get_fingerprint_engine()

        assert engine1 is engine2

    def test_reset_fingerprint_engine(self):
        """Test engine reset clears state."""
        engine = get_fingerprint_engine()
        engine.register_device(device_id="test", device_type="phone")

        assert len(engine.get_device_profiles()) == 1

        reset_fingerprint_engine()

        engine2 = get_fingerprint_engine()
        assert len(engine2.get_device_profiles()) == 0
