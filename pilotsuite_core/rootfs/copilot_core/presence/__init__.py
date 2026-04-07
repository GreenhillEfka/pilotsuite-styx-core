"""Presence Detection Module — PilotSuite Core.

Unified presence detection with multi-sensor fusion:
- mmWave radar (60GHz static + motion detection) — P3-009
- Wi-Fi/BLE fingerprinting — P3-008
- Bayesian sensor fusion
- Zone-aware presence with hold states
- Calendar-aware presence prediction
"""
from __future__ import annotations

from .mmwave_radar import (
    MmWaveEngine,
    MmWaveSensorConfig,
    MmWavePresenceState,
    MmWaveSensorType,
    DetectionMode,
    RadarPoint,
    RadarTarget,
    CalibrationData,
    get_mmwave_engine,
    get_ha_integration,
    reset_mmwave_engine,
    HomeAssistantIntegration,
    TargetTracker,
    fuse_calendar_presence,
)

from .wifi_ble_fingerprint import (
    FingerprintEngine,
    DeviceFingerprintProfile,
    WiFiFingerprint,
    BLEFingerprint,
    PresenceDetection,
    get_fingerprint_engine,
    reset_fingerprint_engine,
    anonymize_mac,
    rssi_to_distance,
)

from .hold_analytics import (
    HoldAnalyticsStore,
    HoldUsageHistoryV1,
    HoldZonePatternsV1,
    HoldEffectivenessMetricsV1,
    HoldAnalyticsSummaryV1,
)

__all__ = [
    # mmWave radar (P3-009)
    "MmWaveEngine",
    "MmWaveSensorConfig",
    "MmWavePresenceState",
    "MmWaveSensorType",
    "DetectionMode",
    "RadarPoint",
    "RadarTarget",
    "CalibrationData",
    "get_mmwave_engine",
    "get_ha_integration",
    "reset_mmwave_engine",
    "HomeAssistantIntegration",
    "TargetTracker",
    "fuse_calendar_presence",
    # Wi-Fi/BLE fingerprinting (P3-008)
    "FingerprintEngine",
    "DeviceFingerprintProfile",
    "WiFiFingerprint",
    "BLEFingerprint",
    "PresenceDetection",
    "get_fingerprint_engine",
    "reset_fingerprint_engine",
    "anonymize_mac",
    "rssi_to_distance",
    # Hold analytics
    "HoldAnalyticsStore",
    "HoldUsageHistoryV1",
    "HoldZonePatternsV1",
    "HoldEffectivenessMetricsV1",
    "HoldAnalyticsSummaryV1",
]

__version__ = "4.2.0"  # Bumped for calendar-aware presence fusion
