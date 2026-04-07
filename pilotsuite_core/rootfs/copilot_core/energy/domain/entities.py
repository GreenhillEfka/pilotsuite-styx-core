"""Domain entities for Energy module.

Entities are the core business objects with identity and lifecycle.
They contain business logic and enforce invariants.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class EnergyUsageEntry:
    """Core domain entity representing a single energy usage measurement.
    
    This is the fundamental unit of energy tracking, capturing consumption
    at a specific point in time for a specific entity.
    """
    id: Optional[int] = None
    timestamp: str = ""
    zone_id: str = ""
    module_id: str = ""
    entity_id: str = ""
    consumption_wh: float = 0.0
    cost_eur: float = 0.0
    tariff_rate: str = "off_peak"  # peak, off_peak, super_off_peak
    source: str = "grid"  # grid, pv, battery
    
    def __post_init__(self):
        """Validate entity invariants."""
        if self.consumption_wh < 0:
            raise ValueError("Consumption cannot be negative")
        if self.cost_eur < 0:
            raise ValueError("Cost cannot be negative")
    
    @property
    def effective_rate(self) -> float:
        """Calculate effective rate in ct/kWh."""
        if self.consumption_wh == 0:
            return 0.0
        return (self.cost_eur / self.consumption_wh) * 1000 * 100
    
    def normalize(self) -> "EnergyUsageEntry":
        """Return a normalized copy with validated values."""
        return EnergyUsageEntry(
            id=self.id,
            timestamp=self.timestamp,
            zone_id=self.zone_id.lower() if self.zone_id else "",
            module_id=self.module_id.lower() if self.module_id else "",
            entity_id=self.entity_id.lower() if self.entity_id else "",
            consumption_wh=max(0, self.consumption_wh),
            cost_eur=max(0, self.cost_eur),
            tariff_rate=self.tariff_rate.lower(),
            source=self.source.lower(),
        )


@dataclass
class ZoneEnergyPattern:
    """Domain entity representing energy consumption patterns for a zone.
    
    Captures learned patterns and trends for energy optimization.
    """
    zone_id: str
    zone_name: str
    avg_daily_consumption_wh: float = 0.0
    peak_hour: int = 0  # 0-23
    peak_consumption_wh: float = 0.0
    off_peak_consumption_wh: float = 0.0
    weekday_pattern: List[float] = field(default_factory=list)  # 24h profile
    weekend_pattern: List[float] = field(default_factory=list)  # 24h profile
    dominant_modules: List[str] = field(default_factory=list)
    trend_7d: float = 0.0  # percentage change
    trend_30d: float = 0.0
    revision: int = 0
    
    def __post_init__(self):
        """Ensure pattern lists are properly initialized."""
        if not self.weekday_pattern:
            self.weekday_pattern = [0.0] * 24
        if not self.weekend_pattern:
            self.weekend_pattern = [0.0] * 24
    
    def update_pattern(self, hour: int, consumption_wh: float, is_weekend: bool) -> None:
        """Update hourly pattern with new data point."""
        if not (0 <= hour <= 23):
            return
        
        pattern = self.weekend_pattern if is_weekend else self.weekday_pattern
        # Simple moving average with weight 0.1 for new data
        pattern[hour] = pattern[hour] * 0.9 + consumption_wh * 0.1
    
    def calculate_trends(self, historical_daily: List[float]) -> None:
        """Calculate 7-day and 30-day trends from historical data."""
        if len(historical_daily) >= 7:
            recent_avg = sum(historical_daily[-7:]) / 7
            older_avg = sum(historical_daily[-14:-7]) / 7 if len(historical_daily) >= 14 else recent_avg
            if older_avg > 0:
                self.trend_7d = ((recent_avg - older_avg) / older_avg) * 100
        
        if len(historical_daily) >= 30:
            recent_avg = sum(historical_daily[-7:]) / 7
            older_avg = sum(historical_daily[-30:-7]) / 23
            if older_avg > 0:
                self.trend_30d = ((recent_avg - older_avg) / older_avg) * 100
    
    @property
    def peak_to_off_peak_ratio(self) -> float:
        """Calculate ratio of peak to off-peak consumption."""
        if self.off_peak_consumption_wh == 0:
            return float('inf') if self.peak_consumption_wh > 0 else 1.0
        return self.peak_consumption_wh / self.off_peak_consumption_wh


@dataclass
class EnergyEffectivenessMetrics:
    """Domain entity tracking energy optimization effectiveness.
    
    Single-instance entity (singleton pattern) for system-wide metrics.
    """
    id: int = 1  # Singleton ID
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
    
    @property
    def suggestion_acceptance_rate(self) -> float:
        """Calculate rate of accepted suggestions."""
        total = self.suggestions_accepted + self.suggestions_rejected
        if total == 0:
            return 0.0
        return self.suggestions_accepted / total
    
    @property
    def total_suggestions(self) -> int:
        """Total suggestions ever made."""
        return self.suggestions_accepted + self.suggestions_rejected + self.suggestions_pending
    
    def record_suggestion_outcome(self, accepted: bool) -> None:
        """Record whether a suggestion was accepted or rejected."""
        if accepted:
            self.suggestions_accepted += 1
        else:
            self.suggestions_rejected += 1
    
    def record_load_shift(self, duration_minutes: float, savings_wh: float) -> None:
        """Record a completed load shift operation."""
        self.load_shifts_executed += 1
        self.total_savings_wh += savings_wh
        
        # Update running average for duration
        total_shifts = self.load_shifts_executed
        self.avg_shift_duration_minutes = (
            (self.avg_shift_duration_minutes * (total_shifts - 1) + duration_minutes)
            / total_shifts
        )
    
    def update_savings(self, savings_eur: float, cumulative: bool = True) -> None:
        """Update savings metrics."""
        if cumulative:
            self.total_savings_eur += savings_eur
        else:
            self.total_savings_eur = savings_eur
    
    def update_efficiency_metrics(
        self,
        success_rate: float,
        peak_reduction: float,
        pv_self_consumption: float,
        battery_eff: float,
    ) -> None:
        """Update core efficiency metrics."""
        self.optimization_success_rate = max(0.0, min(1.0, success_rate))
        self.peak_reduction_percentage = max(0.0, min(100.0, peak_reduction))
        self.pv_self_consumption_rate = max(0.0, min(1.0, pv_self_consumption))
        self.battery_efficiency = max(0.0, min(1.0, battery_eff))
