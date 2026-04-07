"""Weather Analytics — Usage History, Zone Patterns, Effectiveness Metrics — Slice 51."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class WeatherEventType(str, Enum):
    """Weather-Event-Typen für Analytics."""
    TEMPERATURE_CHANGE = "temperature_change"
    PRECIPITATION = "precipitation"
    WIND_ALERT = "wind_alert"
    STORM_WARNING = "storm_warning"
    FROST_WARNING = "frost_warning"
    HEAT_WARNING = "heat_warning"
    UV_INDEX_HIGH = "uv_index_high"
    AIR_QUALITY_ALERT = "air_quality_alert"
    POLLEN_HIGH = "pollen_high"
    HUMIDITY_EXTREME = "humidity_extreme"
    PRESSURE_DROP = "pressure_drop"
    SUNRISE = "sunrise"
    SUNSET = "sunset"


class WeatherDataSource(str, Enum):
    """Source-Typen für Weather-Daten."""
    WTTR_IN = "wttr_in"
    OPEN_METEO = "open_meteo"
    DWD = "dwd"
    MET_NO = "met_no"
    MANUAL = "manual"
    HOME_SENSOR = "home_sensor"
    ZONE_SENSOR = "zone_sensor"
    SCHEDULE = "schedule"
    ALERT_TRIGGER = "alert_trigger"


@dataclass(frozen=True)
class WeatherObservationEntryV1:
    """Einzelner Weather-Observation-Eintrag für Historie."""

    entry_id: str
    zone_id: str
    zone_name: Optional[str]
    event_type: str  # WeatherEventType
    source: str  # WeatherDataSource
    temperature_celsius: Optional[float]
    humidity_percent: Optional[float]
    wind_speed_kmh: Optional[float]
    precipitation_mm: Optional[float]
    pressure_hpa: Optional[float]
    uv_index: Optional[float]
    air_quality_index: Optional[int]
    alert_triggered: bool
    notification_sent: bool
    automation_triggered: bool
    observed_at: str  # ISO-8601
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class WeatherObservationHistoryV1:
    """Aggregierte Weather-Observation-Historie über alle Zonen."""

    entries: List[WeatherObservationEntryV1]
    total_observations: int
    total_alerts: int
    total_notifications: int
    total_automations: int
    avg_temperature_celsius: Optional[float]
    avg_humidity_percent: Optional[float]
    revision: int
    latest_change_at: str
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None


@dataclass(frozen=True)
class WeatherZonePatternEntryV1:
    """Weather-Pattern für eine einzelne Zone."""

    zone_id: str
    zone_name: Optional[str]
    total_observations: int
    temperature_events: int
    precipitation_events: int
    wind_events: int
    alert_events: int
    avg_temperature_celsius: Optional[float]
    min_temperature_celsius: Optional[float]
    max_temperature_celsius: Optional[float]
    avg_humidity_percent: Optional[float]
    avg_wind_speed_kmh: Optional[float]
    total_precipitation_mm: Optional[float]
    observations_last_24_hours: int
    observations_last_7_days: int
    most_common_event_type: Optional[str]
    most_common_source: Optional[str]
    peak_alert_hour: Optional[int]  # 0-23


@dataclass(frozen=True)
class WeatherZonePatternsV1:
    """Zone-spezifische Weather-Patterns."""

    patterns: List[WeatherZonePatternEntryV1]
    total_zones: int
    zones_with_weather_data: int
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class WeatherEffectivenessMetricsV1:
    """Weather-Effectiveness-Metriken."""

    total_observations_analyzed: int
    observations_by_type: Dict[str, int]  # event_type → count
    observations_by_source: Dict[str, int]  # source → count
    alert_accuracy_rate: Optional[float]  # 0.0–1.0 (wenn Feedback verfügbar)
    notification_delivery_rate: float  # 0.0–1.0
    automation_trigger_rate: float  # 0.0–1.0
    avg_observations_per_zone: float
    zones_with_regular_data: int  # >20 observations
    zones_with_rare_data: int  # <=20 observations
    peak_weather_time: Optional[str]  # morning/day/evening/night
    forecast_accuracy_score: Optional[float]  # 0.0–1.0
    engagement_score: float  # 0.0–1.0 composite score
    revision: int
    latest_change_at: str


@dataclass(frozen=True)
class WeatherAnalyticsSummaryV1:
    """Zusammenfassung aller Weather-Analytics."""

    usage: WeatherObservationHistoryV1
    patterns: WeatherZonePatternsV1
    effectiveness: WeatherEffectivenessMetricsV1
    summary_revision: int
    latest_change_at: str
