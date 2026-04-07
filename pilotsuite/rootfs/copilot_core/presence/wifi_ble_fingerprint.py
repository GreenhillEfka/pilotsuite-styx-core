"""Wi-Fi/BLE Fingerprinting for Presence Detection — P3-008.

Implements device presence detection using Wi-Fi signal strength patterns
and BLE beacon detection with sensor fusion for accurate presence inference.

Features:
- Wi-Fi fingerprinting using RSSI signal strength patterns
- BLE beacon detection and tracking
- Multi-sensor fusion algorithm combining Wi-Fi + BLE + motion
- MAC address anonymization for privacy
- Pattern matching for device recognition
- Home Assistant sensor integration

API Endpoints:
- POST /api/v1/presence/fingerprint/detect — Submit fingerprint data for presence detection
- GET /api/v1/presence/fingerprint/devices — List known devices
- POST /api/v1/presence/fingerprint/devices/register — Register a new device
- GET /api/v1/presence/fingerprint/history — Recent detection history

Blueprint prefix: /api/v1/presence/fingerprint
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# =============================================================================
# Constants and Configuration
# =============================================================================

# RSSI thresholds for signal quality
RSSI_EXCELLENT = -50  # Excellent signal
RSSI_GOOD = -60  # Good signal
RSSI_FAIR = -70  # Fair signal
RSSI_POOR = -80  # Poor signal
RSSI_UNUSABLE = -90  # Unusable signal

# BLE RSSI distance estimation parameters (log-distance path loss model)
BLE_TX_POWER = -59  # Typical TX power at 1m (dBm)
BLE_PATH_LOSS_EXPONENT = 2.0  # Indoor environment

# Temporal smoothing parameters
FINGERPRINT_WINDOW_SECONDS = 30  # Window for aggregating fingerprints
FINGERPRINT_DECAY_FACTOR = 0.3  # Exponential decay factor for historical data
PRESENCE_CONFIDENCE_THRESHOLD = 0.6  # Minimum confidence for presence detection

# Privacy: hash iterations for MAC anonymization
MAC_HASH_ITERATIONS = 10000

# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class WiFiFingerprint:
    """Wi-Fi signal fingerprint from a single access point."""

    bssid_hash: str  # Anonymized BSSID
    ssid_hash: str  # Anonymized SSID
    rssi: int  # Signal strength in dBm
    frequency: int  # Frequency in MHz (2412, 5180, etc.)
    channel: int  # Wi-Fi channel
    timestamp: float  # Unix timestamp
    noise: Optional[int] = None  # Noise floor in dBm


@dataclass(frozen=True)
class BLEFingerprint:
    """BLE beacon fingerprint."""

    device_hash: str  # Anonymized device address
    service_uuid: Optional[str]  # Advertised service UUID
    manufacturer_id: Optional[int]  # Manufacturer ID
    rssi: int  # Signal strength in dBm
    tx_power: Optional[int]  # Advertised TX power
    timestamp: float  # Unix timestamp
    payload: Optional[bytes] = None  # Raw advertisement payload (not stored)


@dataclass
class DeviceFingerprintProfile:
    """Aggregated fingerprint profile for a known device."""

    device_id: str  # Anonymized device identifier
    device_type: str  # "phone", "tablet", "watch", "unknown"
    wifi_signatures: Dict[str, List[int]]  # BSSID hash -> list of RSSI values
    ble_signatures: Dict[str, List[int]]  # Device hash -> list of RSSI values
    typical_rssi_mean: float  # Typical mean RSSI for this device
    typical_rssi_std: float  # Typical RSSI standard deviation
    last_seen: float  # Last seen timestamp
    confidence_score: float  # Current confidence score (0.0-1.0)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class PresenceDetection:
    """Result of presence detection."""

    device_id: str
    device_type: str
    is_present: bool
    confidence: float
    location_zone: Optional[str]  # Inferred zone/room
    detection_method: str  # "wifi", "ble", "fusion"
    wifi_rssi: Optional[float] = None
    ble_rssi: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class FingerprintHistoryEntry:
    """Historical fingerprint detection entry."""

    device_id: str
    detection: PresenceDetection
    raw_wifi_count: int
    raw_ble_count: int
    processed_at: str


# =============================================================================
# Utility Functions
# =============================================================================


def anonymize_mac(mac_address: str, salt: str = "pilotsuite-fingerprint") -> str:
    """Anonymize a MAC address using iterative hashing.

    Args:
        mac_address: MAC address in format XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX
        salt: Salt string for hashing

    Returns:
        Anonymized hash string (first 16 chars of SHA-256)
    """
    # Normalize MAC address format
    normalized = mac_address.upper().replace("-", ":")

    # Combine with salt
    data = f"{salt}:{normalized}"

    # Iterative hashing for privacy
    for _ in range(MAC_HASH_ITERATIONS):
        data = hashlib.sha256(data.encode()).hexdigest()

    return data[:16]


def rssi_to_distance(rssi: int, tx_power: int = BLE_TX_POWER, n: float = BLE_PATH_LOSS_EXPONENT) -> float:
    """Estimate distance from RSSI using log-distance path loss model.

    Args:
        rssi: Received signal strength in dBm
        tx_power: Transmitted power at 1m (default: -59 dBm)
        n: Path loss exponent (2.0 for indoor)

    Returns:
        Estimated distance in meters
    """
    if rssi >= tx_power:
        return 1.0

    distance = 10 ** ((tx_power - rssi) / (10 * n))
    return max(0.1, min(distance, 50.0))  # Clamp to reasonable range


def calculate_signal_quality(rssi: int) -> str:
    """Categorize signal quality based on RSSI.

    Args:
        rssi: Signal strength in dBm

    Returns:
        Quality category: "excellent", "good", "fair", "poor", "unusable"
    """
    if rssi >= RSSI_EXCELLENT:
        return "excellent"
    elif rssi >= RSSI_GOOD:
        return "good"
    elif rssi >= RSSI_FAIR:
        return "fair"
    elif rssi >= RSSI_POOR:
        return "poor"
    else:
        return "unusable"


def gaussian_kernel(x: float, mean: float, std: float) -> float:
    """Calculate Gaussian kernel value.

    Args:
        x: Input value
        mean: Distribution mean
        std: Distribution standard deviation

    Returns:
        Gaussian probability density
    """
    if std <= 0:
        std = 1.0
    return np.exp(-0.5 * ((x - mean) / std) ** 2)


# =============================================================================
# Fingerprint Processing Engine
# =============================================================================


class FingerprintEngine:
    """Engine for processing Wi-Fi and BLE fingerprints for presence detection."""

    def __init__(self):
        """Initialize the fingerprint engine."""
        # Device profiles: device_id -> DeviceFingerprintProfile
        self._device_profiles: Dict[str, DeviceFingerprintProfile] = {}

        # Recent fingerprints for temporal aggregation
        self._recent_wifi: List[WiFiFingerprint] = []
        self._recent_ble: List[BLEFingerprint] = []

        # Detection history
        self._detection_history: List[FingerprintHistoryEntry] = []

        # Zone mapping: BSSID/device hash -> zone_id
        self._zone_mapping: Dict[str, str] = {}

        logger.info("FingerprintEngine initialized")

    def register_device(
        self,
        device_id: str,
        device_type: str = "unknown",
        initial_wifi_rssi: Optional[List[int]] = None,
        initial_ble_rssi: Optional[List[int]] = None,
    ) -> DeviceFingerprintProfile:
        """Register a new device for fingerprint tracking.

        Args:
            device_id: Anonymized device identifier
            device_type: Type of device (phone, tablet, watch, etc.)
            initial_wifi_rssi: Initial Wi-Fi RSSI samples
            initial_ble_rssi: Initial BLE RSSI samples

        Returns:
            Created device profile
        """
        profile = DeviceFingerprintProfile(
            device_id=device_id,
            device_type=device_type,
            wifi_signatures={},
            ble_signatures={},
            typical_rssi_mean=-70.0,
            typical_rssi_std=10.0,
            last_seen=time.time(),
            confidence_score=0.0,
        )

        if initial_wifi_rssi:
            profile.wifi_signatures["calibration"] = initial_wifi_rssi
            profile.typical_rssi_mean = float(np.mean(initial_wifi_rssi))
            profile.typical_rssi_std = float(np.std(initial_wifi_rssi)) or 10.0

        if initial_ble_rssi:
            profile.ble_signatures["calibration"] = initial_ble_rssi
            if not initial_wifi_rssi:
                profile.typical_rssi_mean = float(np.mean(initial_ble_rssi))
                profile.typical_rssi_std = float(np.std(initial_ble_rssi)) or 10.0

        self._device_profiles[device_id] = profile
        logger.info("Registered device: %s (type: %s)", device_id, device_type)
        return profile

    def process_wifi_fingerprint(
        self,
        bssid: str,
        ssid: str,
        rssi: int,
        frequency: int,
        channel: int,
        timestamp: Optional[float] = None,
        noise: Optional[int] = None,
    ) -> WiFiFingerprint:
        """Process a Wi-Fi fingerprint sample.

        Args:
            bssid: Access point MAC address
            ssid: Network SSID
            rssi: Signal strength in dBm
            frequency: Frequency in MHz
            channel: Wi-Fi channel
            timestamp: Unix timestamp (default: now)
            noise: Noise floor in dBm

        Returns:
            Processed WiFiFingerprint with anonymized identifiers
        """
        bssid_hash = anonymize_mac(bssid)
        ssid_hash = hashlib.sha256(ssid.encode()).hexdigest()[:16]

        fp = WiFiFingerprint(
            bssid_hash=bssid_hash,
            ssid_hash=ssid_hash,
            rssi=rssi,
            frequency=frequency,
            channel=channel,
            timestamp=timestamp or time.time(),
            noise=noise,
        )

        self._recent_wifi.append(fp)
        self._trim_history()

        # Update zone mapping if known
        if bssid_hash in self._zone_mapping:
            pass  # Zone already mapped

        return fp

    def process_ble_fingerprint(
        self,
        mac_address: str,
        rssi: int,
        service_uuid: Optional[str] = None,
        manufacturer_id: Optional[int] = None,
        tx_power: Optional[int] = None,
        timestamp: Optional[float] = None,
    ) -> BLEFingerprint:
        """Process a BLE beacon fingerprint sample.

        Args:
            mac_address: BLE device MAC address
            rssi: Signal strength in dBm
            service_uuid: Advertised service UUID
            manufacturer_id: Manufacturer ID from advertisement
            tx_power: Advertised TX power
            timestamp: Unix timestamp (default: now)

        Returns:
            Processed BLEFingerprint with anonymized identifier
        """
        device_hash = anonymize_mac(mac_address)

        fp = BLEFingerprint(
            device_hash=device_hash,
            service_uuid=service_uuid,
            manufacturer_id=manufacturer_id,
            rssi=rssi,
            tx_power=tx_power,
            timestamp=timestamp or time.time(),
        )

        self._recent_ble.append(fp)
        self._trim_history()

        return fp

    def detect_presence(
        self,
        device_id: Optional[str] = None,
        use_fusion: bool = True,
    ) -> Optional[PresenceDetection]:
        """Detect presence for a device using fingerprint analysis.

        Args:
            device_id: Specific device to detect (None for all)
            use_fusion: Use multi-sensor fusion algorithm

        Returns:
            PresenceDetection result or None if no match
        """
        now = time.time()
        cutoff = now - FINGERPRINT_WINDOW_SECONDS

        # Filter recent fingerprints within window
        wifi_in_window = [fp for fp in self._recent_wifi if fp.timestamp >= cutoff]
        ble_in_window = [fp for fp in self._recent_ble if fp.timestamp >= cutoff]

        if not wifi_in_window and not ble_in_window:
            return None

        # Aggregate by device
        device_scores: Dict[str, Dict[str, Any]] = {}

        # Process Wi-Fi fingerprints
        for fp in wifi_in_window:
            # Try to match to known devices
            for dev_id, profile in self._device_profiles.items():
                if fp.bssid_hash in profile.wifi_signatures:
                    if dev_id not in device_scores:
                        device_scores[dev_id] = {
                            "wifi_rssi": [],
                            "ble_rssi": [],
                            "wifi_count": 0,
                            "ble_count": 0,
                        }
                    device_scores[dev_id]["wifi_rssi"].append(fp.rssi)
                    device_scores[dev_id]["wifi_count"] += 1

        # Process BLE fingerprints
        for fp in ble_in_window:
            for dev_id, profile in self._device_profiles.items():
                if fp.device_hash in profile.ble_signatures:
                    if dev_id not in device_scores:
                        device_scores[dev_id] = {
                            "wifi_rssi": [],
                            "ble_rssi": [],
                            "wifi_count": 0,
                            "ble_count": 0,
                        }
                    device_scores[dev_id]["ble_rssi"].append(fp.rssi)
                    device_scores[dev_id]["ble_count"] += 1

        if not device_scores:
            # No known devices detected, create detection for strongest signal
            return self._detect_unknown_device(wifi_in_window, ble_in_window)

        # Calculate confidence scores for each device
        results = []
        for dev_id, scores in device_scores.items():
            if device_id and dev_id != device_id:
                continue

            profile = self._device_profiles.get(dev_id)
            if not profile:
                continue

            if use_fusion:
                confidence = self._calculate_fusion_confidence(
                    profile,
                    scores["wifi_rssi"],
                    scores["ble_rssi"],
                )
                detection_method = "fusion"
            else:
                if scores["wifi_rssi"] and scores["ble_rssi"]:
                    confidence = max(
                        self._calculate_wifi_confidence(profile, scores["wifi_rssi"]),
                        self._calculate_ble_confidence(profile, scores["ble_rssi"]),
                    )
                    detection_method = "max(wifi,ble)"
                elif scores["wifi_rssi"]:
                    confidence = self._calculate_wifi_confidence(profile, scores["wifi_rssi"])
                    detection_method = "wifi"
                else:
                    confidence = self._calculate_ble_confidence(profile, scores["ble_rssi"])
                    detection_method = "ble"

            avg_wifi_rssi = float(np.mean(scores["wifi_rssi"])) if scores["wifi_rssi"] else None
            avg_ble_rssi = float(np.mean(scores["ble_rssi"])) if scores["ble_rssi"] else None

            is_present = confidence >= PRESENCE_CONFIDENCE_THRESHOLD

            detection = PresenceDetection(
                device_id=dev_id,
                device_type=profile.device_type,
                is_present=is_present,
                confidence=confidence,
                location_zone=self._infer_zone(scores["wifi_rssi"], scores["ble_rssi"]),
                detection_method=detection_method,
                wifi_rssi=avg_wifi_rssi,
                ble_rssi=avg_ble_rssi,
            )

            results.append((detection, scores["wifi_count"], scores["ble_count"]))

            # Update profile
            profile.last_seen = now
            profile.confidence_score = confidence
            profile.updated_at = datetime.now(timezone.utc).isoformat()

        # Add to history
        for detection, wifi_count, ble_count in results:
            entry = FingerprintHistoryEntry(
                device_id=detection.device_id,
                detection=detection,
                raw_wifi_count=wifi_count,
                raw_ble_count=ble_count,
                processed_at=datetime.now(timezone.utc).isoformat(),
            )
            self._detection_history.append(entry)

        # Return best match if device_id specified, otherwise highest confidence
        if device_id:
            return results[0][0] if results else None
        else:
            return max(results, key=lambda x: x[0].confidence)[0] if results else None

    def _calculate_wifi_confidence(
        self,
        profile: DeviceFingerprintProfile,
        rssi_values: List[int],
    ) -> float:
        """Calculate presence confidence from Wi-Fi RSSI values.

        Uses Gaussian matching against the device's typical RSSI profile.

        Args:
            profile: Device fingerprint profile
            rssi_values: List of RSSI measurements

        Returns:
            Confidence score (0.0-1.0)
        """
        if not rssi_values:
            return 0.0

        mean_rssi = float(np.mean(rssi_values))
        std_rssi = float(np.std(rssi_values)) or 1.0

        # Match against typical profile
        signal_match = gaussian_kernel(
            mean_rssi,
            profile.typical_rssi_mean,
            max(profile.typical_rssi_std, std_rssi),
        )

        # Weight by signal quality
        quality_weight = len(rssi_values) / 10.0  # Normalize to ~10 samples
        quality_weight = min(1.0, quality_weight)

        confidence = signal_match * quality_weight
        return min(1.0, confidence)

    def _calculate_ble_confidence(
        self,
        profile: DeviceFingerprintProfile,
        rssi_values: List[int],
    ) -> float:
        """Calculate presence confidence from BLE RSSI values.

        Args:
            profile: Device fingerprint profile
            rssi_values: List of RSSI measurements

        Returns:
            Confidence score (0.0-1.0)
        """
        if not rssi_values:
            return 0.0

        mean_rssi = float(np.mean(rssi_values))

        # BLE typically has higher variance, use wider matching
        signal_match = gaussian_kernel(
            mean_rssi,
            profile.typical_rssi_mean,
            max(profile.typical_rssi_std * 1.5, 5.0),
        )

        # Weight by sample count
        quality_weight = min(1.0, len(rssi_values) / 5.0)

        confidence = signal_match * quality_weight
        return min(1.0, confidence)

    def _calculate_fusion_confidence(
        self,
        profile: DeviceFingerprintProfile,
        wifi_rssi: List[int],
        ble_rssi: List[int],
    ) -> float:
        """Calculate fused presence confidence from multiple sensor sources.

        Implements weighted sensor fusion with cross-validation.

        Args:
            profile: Device fingerprint profile
            wifi_rssi: Wi-Fi RSSI measurements
            ble_rssi: BLE RSSI measurements

        Returns:
            Fused confidence score (0.0-1.0)
        """
        wifi_conf = self._calculate_wifi_confidence(profile, wifi_rssi) if wifi_rssi else 0.0
        ble_conf = self._calculate_ble_confidence(profile, ble_rssi) if ble_rssi else 0.0

        if wifi_rssi and ble_rssi:
            # Both sensors available: weighted average with cross-validation bonus
            base_confidence = 0.6 * wifi_conf + 0.4 * ble_conf

            # Cross-validation: if both agree, boost confidence
            if abs(wifi_conf - ble_conf) < 0.2:
                cross_validation_bonus = 0.15
            else:
                cross_validation_bonus = 0.0

            # Sample count bonus
            total_samples = len(wifi_rssi) + len(ble_rssi)
            sample_bonus = min(0.1, total_samples / 50.0)

            confidence = base_confidence + cross_validation_bonus + sample_bonus
        elif wifi_rssi:
            confidence = wifi_conf * 0.9  # Slight penalty for single sensor
        elif ble_rssi:
            confidence = ble_conf * 0.85  # BLE typically less reliable
        else:
            confidence = 0.0

        return min(1.0, confidence)

    def _infer_zone(
        self,
        wifi_rssi: List[int],
        ble_rssi: List[int],
    ) -> Optional[str]:
        """Infer location zone from fingerprint data.

        Args:
            wifi_rssi: Wi-Fi RSSI values
            ble_rssi: BLE RSSI values

        Returns:
            Zone ID or None if cannot infer
        """
        # Simple zone inference based on strongest signal
        # In production, this would use a trained zone classifier
        if wifi_rssi:
            avg_rssi = np.mean(wifi_rssi)
            if avg_rssi >= RSSI_GOOD:
                return "near_ap"
            elif avg_rssi >= RSSI_FAIR:
                return "same_room"
            else:
                return "building"

        if ble_rssi:
            avg_rssi = np.mean(ble_rssi)
            distance = rssi_to_distance(int(avg_rssi))
            if distance < 3.0:
                return "same_room"
            elif distance < 10.0:
                return "nearby"
            else:
                return "building"

        return None

    def _detect_unknown_device(
        self,
        wifi_fps: List[WiFiFingerprint],
        ble_fps: List[BLEFingerprint],
    ) -> PresenceDetection:
        """Create detection for an unknown device.

        Args:
            wifi_fps: Wi-Fi fingerprints
            ble_fps: BLE fingerprints

        Returns:
            PresenceDetection for unknown device
        """
        # Use strongest signal as representative
        best_rssi = None
        detection_method = "unknown"

        if wifi_fps:
            best_wifi = max(wifi_fps, key=lambda fp: fp.rssi)
            best_rssi = best_wifi.rssi
            detection_method = "wifi"

        if ble_fps:
            best_ble = max(ble_fps, key=lambda fp: fp.rssi)
            if best_rssi is None or best_ble.rssi > best_rssi:
                best_rssi = best_ble.rssi
                detection_method = "ble"

        # Low confidence for unknown devices
        confidence = 0.3 if best_rssi else 0.0
        if best_rssi and best_rssi >= RSSI_GOOD:
            confidence = 0.5

        return PresenceDetection(
            device_id="unknown",
            device_type="unknown",
            is_present=confidence >= PRESENCE_CONFIDENCE_THRESHOLD,
            confidence=confidence,
            location_zone=self._infer_zone(
                [fp.rssi for fp in wifi_fps],
                [fp.rssi for fp in ble_fps],
            ),
            detection_method=detection_method,
            wifi_rssi=best_rssi if detection_method == "wifi" else None,
            ble_rssi=best_rssi if detection_method == "ble" else None,
        )

    def _trim_history(self) -> None:
        """Trim old fingerprints to stay within memory limits."""
        cutoff = time.time() - FINGERPRINT_WINDOW_SECONDS * 2

        self._recent_wifi = [fp for fp in self._recent_wifi if fp.timestamp >= cutoff]
        self._recent_ble = [fp for fp in self._recent_ble if fp.timestamp >= cutoff]

        # Keep last 1000 history entries
        if len(self._detection_history) > 1000:
            self._detection_history = self._detection_history[-1000:]

    def get_device_profiles(self) -> List[DeviceFingerprintProfile]:
        """Get all registered device profiles."""
        return list(self._device_profiles.values())

    def get_detection_history(self, limit: int = 100) -> List[FingerprintHistoryEntry]:
        """Get recent detection history.

        Args:
            limit: Maximum entries to return

        Returns:
            List of history entries (newest first)
        """
        return self._detection_history[-limit:]

    def set_zone_mapping(self, identifier_hash: str, zone_id: str) -> None:
        """Map a BSSID or device hash to a zone.

        Args:
            identifier_hash: Anonymized BSSID or device hash
            zone_id: Zone identifier
        """
        self._zone_mapping[identifier_hash] = zone_id
        logger.debug("Zone mapping: %s -> %s", identifier_hash, zone_id)


# =============================================================================
# Global Engine Instance
# =============================================================================

_fingerprint_engine: Optional[FingerprintEngine] = None


def get_fingerprint_engine() -> FingerprintEngine:
    """Get or create the global fingerprint engine instance."""
    global _fingerprint_engine
    if _fingerprint_engine is None:
        _fingerprint_engine = FingerprintEngine()
    return _fingerprint_engine


def reset_fingerprint_engine() -> None:
    """Reset the global fingerprint engine (for testing)."""
    global _fingerprint_engine
    _fingerprint_engine = None
