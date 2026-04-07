"""Camera Analytics — Usage History, Zone Patterns, Effectiveness Metrics — Slice 50."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class CameraEventType(str, Enum):
    """Camera-Event-Typen für Analytics."""
    MOTION_DETECTED = "motion_detected"
    PERSON_DETECTED = "person_detected"
    VEHICLE_DETECTED = "vehicle_detected"
    SOUND_DETECTED = "sound_detected"
    SNAPSHOT_CAPTURED = "snapshot_captured"
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    DOORBELL_PRESSED = "doorbell_pressed"
    PACKAGE_DETECTED = "package_detected"


class CameraSource(str, Enum):
    """Source-Typen für Camera-Events."""
    MANUAL = "manual"
    AUTO_MOTION = "auto_motion"
    AUTO_PERSON = "auto_person"
    SCHEDULE = "schedule"
    VOICE = "voice"
    PROPOSAL = "proposal"
    SCENE = "scene"
    ROUTINE = "routine"
    ALERT_TRIGGER = "alert_trigger"


@dataclass(frozen=True)
class CameraUsageEntryV1:
    """Einzelner Camera-Usage-Eintrag für Historie."""

    entry_id: str
    zone_id: str
    zone_name: Optional[str]
    camera_id: str
    camera_name: str
    event_type: str  # CameraEventType
    source: str  # CameraSource
    snapshot_taken: bool
    recording_started: bool
    recording_duration_seconds: Optional[int]  # None wenn kein Recording oder noch läuft
    thumbnail_generated: bool
    notification_sent: bool
    processed_at: str  # ISO-8601
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class CameraUsageHistoryV1:
    """Aggregierte Camera-Usage-Historie über alle Zonen."""

    entries: List[CameraUsageEntryV1]
    total_events: int
    total_snapshots: int
    total_recordings: int
    total_recording_duration_seconds: int
    avg_recording_duration_seconds: Optional[float]
    revision: int
    latest_change_at: str
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None


@dataclass(frozen=True)
class CameraZonePatternEntryV1:
    """Camera-Pattern für eine einzelne Zone."""

    zone_id: str
    zone_name: Optional[str]
    total_events: int
    motion_events: int
    person_events: int
    vehicle_events: int
    sound_events: int
    doorbell_events: int
    snapshots_taken: int
    recordings_started: int
    avg_recording_duration_seconds: Optional[float]
    peak_activity_hour: Optional[int]  # 0-23
    events_last_24_hours: int
    events_last_7_days: int
    most_common_event_type: Optional[str]
    most_common_source: Optional[str]


@dataclass(frozen=True)
class CameraZonePatternsV1:
    """Zone-spezifische Camera-Patterns."""

    patterns: List[CameraZonePatternEntryV1]
    total_zones: int
    zones_with_camera_activity: int
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class CameraEffectivenessMetricsV1:
    """Camera-Effectiveness-Metriken."""

    total_events_analyzed: int
    events_by_type: Dict[str, int]  # event_type → count
    events_by_source: Dict[str, int]  # source → count
    motion_to_person_ratio: float  # person_events / motion_events
    false_positive_rate: Optional[float]  # 0.0–1.0 (wenn Feedback verfügbar)
    notification_delivery_rate: float  # 0.0–1.0
    snapshot_capture_rate: float  # snapshots / events
    recording_trigger_rate: float  # recordings / events
    avg_events_per_zone: float
    zones_with_regular_activity: int  # >10 events
    zones_with_rare_activity: int  # <=10 events
    peak_activity_time: Optional[str]  # morning/day/evening/night
    engagement_score: float  # 0.0–1.0 composite score
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class CameraAnalyticsSummaryV1:
    """Zusammenfassung aller Camera-Analytics."""

    usage: CameraUsageHistoryV1
    patterns: CameraZonePatternsV1
    effectiveness: CameraEffectivenessMetricsV1
    summary_revision: int
    latest_change_at: str
