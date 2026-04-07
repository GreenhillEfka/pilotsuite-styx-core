"""Energy Analytics Types — shared definitions."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


class EnergyAnalyticsPeriod(Enum):
    """Analytics period types."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class EnergyUsageEntryV1:
    """Single energy usage entry for analytics."""
    timestamp: str
    zone_id: str
    module_id: str
    entity_id: str
    consumption_wh: float
    cost_eur: float
    tariff_rate: str
    source: str


@dataclass
class EnergyUsageHistoryV1:
    """Energy usage history read model."""
    period: EnergyAnalyticsPeriod
    start_at: str
    end_at: str
    entries: List[EnergyUsageEntryV1] = field(default_factory=list)
    total_consumption_wh: float = 0.0
    total_cost_eur: float = 0.0
    revision: int = 0
    latest_change_at: Optional[str] = None


@dataclass
class ZoneEnergyPatternV1:
    """Energy pattern for a specific zone."""
    zone_id: str
    zone_name: str
    avg_daily_consumption_wh: float
    peak_hour: int
    peak_consumption_wh: float
    off_peak_consumption_wh: float
    weekday_pattern: List[float] = field(default_factory=list)
    weekend_pattern: List[float] = field(default_factory=list)
    dominant_modules: List[str] = field(default_factory=list)
    trend_7d: float = 0.0
    trend_30d: float = 0.0
    revision: int = 0


@dataclass
class EnergyZonePatternsV1:
    """Zone-specific energy patterns read model."""
    patterns: List[ZoneEnergyPatternV1] = field(default_factory=list)
    revision: int = 0
    latest_change_at: Optional[str] = None


@dataclass
class EnergyEffectivenessMetricsV1:
    """Energy optimization effectiveness metrics."""
    total_savings_eur: float = 0.0
    total_savings_wh: float = 0.0
    optimization_success_rate: float = 0.0
    avg_shift_duration_minutes: float = 0.0
    peak_reduction_percentage: float = 0.0
    pv_self_consumption_rate: float = 0.0
    battery_efficiency: float = 0.0
    suggestions_accepted: int = 0
    suggestions_rejected: int = 0
    suggestions_pending: int = 0
    load_shifts_executed: int = 0
    revision: int = 0
    latest_change_at: Optional[str] = None


__all__ = [
    "EnergyAnalyticsPeriod",
    "EnergyUsageEntryV1",
    "EnergyUsageHistoryV1",
    "ZoneEnergyPatternV1",
    "EnergyZonePatternsV1",
    "EnergyEffectivenessMetricsV1",
]
