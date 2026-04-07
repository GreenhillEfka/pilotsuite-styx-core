"""Energy Analytics Read Models — Slice 47."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


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
    tariff_rate: str  # peak, off_peak, super_off_peak
    source: str  # grid, pv, battery


@dataclass
class EnergyUsageHistoryV1:
    """Energy usage history read model."""
    period: EnergyAnalyticsPeriod
    start_at: str
    end_at: str
    entries: list[EnergyUsageEntryV1] = field(default_factory=list)
    total_consumption_wh: float = 0.0
    total_cost_eur: float = 0.0
    revision: int = 0
    latest_change_at: Optional[str] = None
    
    def add_entry(self, entry: EnergyUsageEntryV1) -> None:
        """Add entry and update totals."""
        self.entries.append(entry)
        self.total_consumption_wh += entry.consumption_wh
        self.total_cost_eur += entry.cost_eur
        self.latest_change_at = datetime.utcnow().isoformat() + "Z"
        self.revision += 1


@dataclass
class ZoneEnergyPatternV1:
    """Energy pattern for a specific zone."""
    zone_id: str
    zone_name: str
    avg_daily_consumption_wh: float
    peak_hour: int  # 0-23
    peak_consumption_wh: float
    off_peak_consumption_wh: float
    weekday_pattern: list[float] = field(default_factory=list)  # 24h profile
    weekend_pattern: list[float] = field(default_factory=list)  # 24h profile
    dominant_modules: list[str] = field(default_factory=list)
    trend_7d: float = 0.0  # percentage change
    trend_30d: float = 0.0
    revision: int = 0


@dataclass
class EnergyZonePatternsV1:
    """Zone-specific energy patterns read model."""
    patterns: list[ZoneEnergyPatternV1] = field(default_factory=list)
    revision: int = 0
    latest_change_at: Optional[str] = None
    
    def add_pattern(self, pattern: ZoneEnergyPatternV1) -> None:
        """Add pattern and update revision."""
        pattern.revision = self.revision + 1
        self.patterns.append(pattern)
        self.latest_change_at = datetime.utcnow().isoformat() + "Z"
        self.revision += 1


@dataclass
class EnergyEffectivenessMetricsV1:
    """Energy optimization effectiveness metrics."""
    total_savings_eur: float = 0.0
    total_savings_wh: float = 0.0
    optimization_success_rate: float = 0.0  # 0.0-1.0
    avg_shift_duration_minutes: float = 0.0
    peak_reduction_percentage: float = 0.0
    pv_self_consumption_rate: float = 0.0  # 0.0-1.0
    battery_efficiency: float = 0.0  # 0.0-1.0
    suggestions_accepted: int = 0
    suggestions_rejected: int = 0
    suggestions_pending: int = 0
    load_shifts_executed: int = 0
    revision: int = 0
    latest_change_at: Optional[str] = None
    
    def update_metrics(self, savings_eur: float, savings_wh: float, 
                       success_rate: float, peak_reduction: float) -> None:
        """Update core metrics and increment revision."""
        self.total_savings_eur = savings_eur
        self.total_savings_wh = savings_wh
        self.optimization_success_rate = success_rate
        self.peak_reduction_percentage = peak_reduction
        self.latest_change_at = datetime.utcnow().isoformat() + "Z"
        self.revision += 1


@dataclass
class EnergyAnalyticsSummaryV1:
    """Aggregated energy analytics summary."""
    period: EnergyAnalyticsPeriod
    start_at: str
    end_at: str
    total_consumption_wh: float = 0.0
    total_cost_eur: float = 0.0
    avg_daily_consumption_wh: float = 0.0
    peak_consumption_wh: float = 0.0
    peak_hour: int = 0
    zone_count: int = 0
    module_count: int = 0
    entity_count: int = 0
    pv_generation_wh: float = 0.0
    battery_cycles: int = 0
    grid_import_wh: float = 0.0
    grid_export_wh: float = 0.0
    revision: int = 0
    latest_change_at: Optional[str] = None
    
    def update_revision(self) -> None:
        """Increment revision and update timestamp."""
        self.revision += 1
        self.latest_change_at = datetime.utcnow().isoformat() + "Z"
