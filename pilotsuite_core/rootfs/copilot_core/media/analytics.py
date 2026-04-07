"""Music/Media Analytics — Usage History, Zone Patterns, Effectiveness Metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class MusicMediaType(str, Enum):
    """Media-Typen für Analytics."""
    SONOS_FAVORITE = "sonos_favorite"
    SONOS_RADIO = "sonos_radio"
    SONOS_PLAYLIST = "sonos_playlist"
    MUSIKWOLKE = "musikwolke"
    CAMERA_SNAPSHOT = "camera_snapshot"
    CAMERA_RECORDING = "camera_recording"


class MusicSource(str, Enum):
    """Source-Typen für Media-Events."""
    MANUAL = "manual"
    AUTO_PRESENCE = "auto_presence"
    SCHEDULE = "schedule"
    VOICE = "voice"
    PROPOSAL = "proposal"
    SCENE = "scene"
    ROUTINE = "routine"


@dataclass(frozen=True)
class MusicUsageEntryV1:
    """Einzelner Music-Usage-Eintrag für Historie."""

    entry_id: str
    zone_id: str
    zone_name: Optional[str]
    media_type: str  # MusicMediaType
    media_id: str  # favorite_id, playlist_id, etc.
    media_name: str  # menschlesbarer Name
    player_id: Optional[str]
    source: str  # MusicSource
    volume: int
    duration_seconds: Optional[int]  # None wenn noch läuft
    started_at: str  # ISO-8601
    ended_at: Optional[str]  # ISO-8601 oder None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class MusicUsageHistoryV1:
    """Aggregierte Music-Usage-Historie über alle Zonen."""

    entries: List[MusicUsageEntryV1]
    total_sessions: int
    total_duration_seconds: int
    avg_duration_seconds: Optional[float]
    total_sonos_sessions: int
    total_musikwolke_sessions: int
    revision: int
    latest_change_at: str
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None


@dataclass(frozen=True)
class MusicZonePatternEntryV1:
    """Music-Pattern für eine einzelne Zone."""

    zone_id: str
    zone_name: Optional[str]
    total_sessions: int
    avg_session_duration_seconds: Optional[float]
    most_used_media_type: Optional[str]
    most_common_source: Optional[str]
    avg_volume: float
    peak_listening_hour: Optional[int]  # 0-23
    sessions_last_7_days: int
    sessions_last_30_days: int
    favorite_media: List[str]  # Top 3


@dataclass(frozen=True)
class MusicZonePatternsV1:
    """Zone-spezifische Music-Patterns."""

    patterns: List[MusicZonePatternEntryV1]
    total_zones: int
    zones_with_music: int
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class MusicEffectivenessMetricsV1:
    """Music-Effectiveness-Metriken."""

    total_sessions_analyzed: int
    sessions_by_source: Dict[str, int]  # source → count
    auto_presence_acceptance_rate: float  # 0.0–1.0
    schedule_reliability: float  # 0.0–1.0
    avg_volume_by_time_of_day: Dict[str, float]  # morning/day/evening/night → avg volume
    zones_with_regular_usage: int
    zones_with_rare_usage: int
    favorite_diversity_score: float  # 0.0–1.0 (wie vielfältig sind die Favorites)
    engagement_score: float  # 0.0–1.0 composite score
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class MusicAnalyticsSummaryV1:
    """Zusammenfassung aller Music-Analytics."""

    usage: MusicUsageHistoryV1
    patterns: MusicZonePatternsV1
    effectiveness: MusicEffectivenessMetricsV1
    summary_revision: int
    latest_change_at: str
