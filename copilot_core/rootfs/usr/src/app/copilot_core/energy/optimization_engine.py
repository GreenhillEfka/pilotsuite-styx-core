"""Energy Optimization Engine — Slice 13.

Optimizes energy consumption across all zones/modules.

Features:
- Energy monitoring per module/zone
- Optimization suggestions (policy-gated)
- Tariff-aware scheduling (time-of-use pricing)
- Energy reports + savings tracking
- Load balancing across zones
- Peak demand reduction
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class EnergyUnit(Enum):
    """Energy measurement units."""
    WH = "Wh"  # Watt-hours
    KWH = "kWh"  # Kilowatt-hours
    W = "W"  # Watts (power)
    KW = "kW"  # Kilowatts (power)


class OptimizationType(Enum):
    """Type of optimization suggestion."""
    SCHEDULE_SHIFT = "schedule_shift"  # Move consumption to off-peak
    LOAD_REDUCTION = "load_reduction"  # Reduce consumption
    LOAD_BALANCING = "load_balancing"  # Distribute load across zones
    PEAK_SHAVING = "peak_shaving"  # Reduce peak demand
    EFFICIENCY_IMPROVEMENT = "efficiency_improvement"  # Improve efficiency
    RENEWABLE_ALIGNMENT = "renewable_alignment"  # Align with renewable generation


@dataclass
class EnergyReading:
    """Single energy reading."""
    entity_id: str
    zone_id: str
    module_id: str
    value: float  # Energy value
    unit: EnergyUnit
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    cost: Optional[float] = None  # Cost in currency
    tariff_rate: Optional[str] = None  # e.g., "peak", "off_peak", "super_off_peak"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "value": self.value,
            "unit": self.unit.value,
            "timestamp": self.timestamp,
            "cost": self.cost,
            "tariff_rate": self.tariff_rate,
        }


@dataclass
class OptimizationSuggestion:
    """Energy optimization suggestion."""
    suggestion_id: str
    optimization_type: OptimizationType
    zone_id: str
    module_id: str
    description: str
    estimated_savings: float  # Estimated savings in currency or kWh
    estimated_savings_unit: str  # "EUR" or "kWh"
    confidence: float  # 0.0-1.0 confidence in suggestion
    action_required: Dict[str, Any]  # Action to take
    expires_at: Optional[str] = None
    accepted: bool = False
    rejected: bool = False
    feedback: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "optimization_type": self.optimization_type.value,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "description": self.description,
            "estimated_savings": self.estimated_savings,
            "estimated_savings_unit": self.estimated_savings_unit,
            "confidence": self.confidence,
            "action_required": self.action_required,
            "expires_at": self.expires_at,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "feedback": self.feedback,
        }


@dataclass
class TariffPeriod:
    """Time-of-use tariff period."""
    name: str  # e.g., "peak", "off_peak", "super_off_peak"
    start_hour: int  # 0-23
    end_hour: int  # 0-23
    rate: float  # Cost per kWh
    days: List[str] = field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri"])  # Days of week


class EnergyOptimizationEngine:
    """Main energy optimization engine."""

    def __init__(self):
        self._readings: Dict[str, List[EnergyReading]] = {}
        self._suggestions: Dict[str, OptimizationSuggestion] = {}
        self._tariff_periods: List[TariffPeriod] = []
        self._suggestion_counter = 0

        # Default tariff (can be customized)
        self._default_tariff = [
            TariffPeriod("peak", 17, 21, 0.35, ["mon", "tue", "wed", "thu", "fri"]),
            TariffPeriod("off_peak", 7, 17, 0.25, ["mon", "tue", "wed", "thu", "fri"]),
            TariffPeriod("super_off_peak", 21, 7, 0.15, ["mon", "tue", "wed", "thu", "fri"]),
            TariffPeriod("weekend_off_peak", 0, 24, 0.15, ["sat", "sun"]),
        ]

        # Energy thresholds
        self._high_consumption_threshold_w = 1000  # 1kW
        self._peak_demand_threshold_w = 3000  # 3kW

    def _parse_timestamp(self, timestamp: str) -> datetime:
        """Parse ISO timestamps, including trailing Z values."""
        normalized = timestamp.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _active_tariff_periods(self) -> List[TariffPeriod]:
        """Return custom tariff periods when configured, otherwise defaults."""
        return self._tariff_periods or self._default_tariff

    def add_reading(self, reading: EnergyReading) -> None:
        """Add energy reading."""
        entity_id = reading.entity_id

        if entity_id not in self._readings:
            self._readings[entity_id] = []

        self._readings[entity_id].append(reading)

        # Keep last 1000 readings per entity
        if len(self._readings[entity_id]) > 1000:
            self._readings[entity_id] = self._readings[entity_id][-1000:]

        # Detect optimization opportunities
        self._detect_optimization_opportunities(reading)

    def _detect_optimization_opportunities(self, reading: EnergyReading) -> None:
        """Detect optimization opportunities from a reading."""
        current_dt = self._parse_timestamp(reading.timestamp)
        current_hour = current_dt.hour
        current_day = current_dt.strftime("%a").lower()[:3]

        # Find current tariff period
        current_tariff = self._get_tariff_for_time(current_hour, current_day)

        if current_tariff and current_tariff.name == "peak" and reading.value > self._high_consumption_threshold_w:
            self._create_schedule_shift_suggestion(reading, current_tariff)

    def _get_tariff_for_time(self, hour: int, day: str) -> Optional[TariffPeriod]:
        """Get tariff period for a given time."""
        for period in self._active_tariff_periods():
            if day in period.days:
                if period.start_hour < period.end_hour:
                    # Normal range (e.g., 7-17)
                    if period.start_hour <= hour < period.end_hour:
                        return period
                else:
                    # Overnight range (e.g., 21-7)
                    if hour >= period.start_hour or hour < period.end_hour:
                        return period
        return None
    
    def _create_schedule_shift_suggestion(self, reading: EnergyReading, current_tariff: TariffPeriod) -> None:
        """Create schedule shift suggestion."""
        self._suggestion_counter += 1
        
        # Find cheaper tariff period
        cheaper_periods = [p for p in self._default_tariff if p.rate < current_tariff.rate]
        
        if not cheaper_periods:
            return
        
        best_period = min(cheaper_periods, key=lambda p: p.rate)
        
        # Calculate potential savings
        power_kwh = reading.value / 1000.0  # Convert W to kWh
        rate_diff = current_tariff.rate - best_period.rate
        estimated_savings = power_kwh * rate_diff
        
        suggestion = OptimizationSuggestion(
            suggestion_id=f"opt_{self._suggestion_counter}",
            optimization_type=OptimizationType.SCHEDULE_SHIFT,
            zone_id=reading.zone_id,
            module_id=reading.module_id,
            description=f"Shift {reading.entity_id} from {current_tariff.name} ({current_tariff.rate:.2f}/kWh) to {best_period.name} ({best_period.rate:.2f}/kWh)",
            estimated_savings=estimated_savings,
            estimated_savings_unit="EUR",
            confidence=0.8,
            action_required={
                "action": "schedule_shift",
                "entity_id": reading.entity_id,
                "from_period": current_tariff.name,
                "to_period": best_period.name,
                "best_start_hour": best_period.start_hour,
            },
        )
        
        self._suggestions[suggestion.suggestion_id] = suggestion
    
    def get_energy_summary(self, zone_id: Optional[str] = None, period_hours: int = 24) -> Dict[str, Any]:
        """Get energy consumption summary."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=period_hours)

        total_consumption_wh = 0.0
        total_cost = 0.0
        entity_count = 0
        zone_consumption: Dict[str, float] = defaultdict(float)
        module_consumption: Dict[str, float] = defaultdict(float)
        latest_timestamp: Optional[str] = None

        for readings in self._readings.values():
            recent_readings = [r for r in readings if self._parse_timestamp(r.timestamp) > cutoff]

            if zone_id:
                recent_readings = [r for r in recent_readings if r.zone_id == zone_id]

            if not recent_readings:
                continue

            entity_consumption = sum(r.value for r in recent_readings)
            entity_cost = sum(r.cost or 0.0 for r in recent_readings)

            total_consumption_wh += entity_consumption
            total_cost += entity_cost
            entity_count += 1

            for reading in recent_readings:
                zone_consumption[reading.zone_id] += reading.value
                module_consumption[reading.module_id] += reading.value
                if latest_timestamp is None or self._parse_timestamp(reading.timestamp) > self._parse_timestamp(latest_timestamp):
                    latest_timestamp = reading.timestamp

        return {
            "zone_id": zone_id,
            "total_consumption_wh": total_consumption_wh,
            "total_consumption_kwh": total_consumption_wh / 1000.0,
            "total_cost": total_cost,
            "entity_count": entity_count,
            "period_hours": period_hours,
            "zone_consumption": dict(zone_consumption),
            "module_consumption": dict(module_consumption),
            "average_power_w": total_consumption_wh / period_hours if period_hours > 0 else 0.0,
            "latest_timestamp": latest_timestamp,
        }

    def get_suggestions(
        self,
        unresolved_only: bool = True,
        optimization_type: Optional[OptimizationType | str] = None,
        zone_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get optimization suggestions."""
        suggestions = list(self._suggestions.values())

        if unresolved_only:
            suggestions = [s for s in suggestions if not s.accepted and not s.rejected]

        if optimization_type:
            opt_value = optimization_type.value if isinstance(optimization_type, OptimizationType) else str(optimization_type)
            suggestions = [s for s in suggestions if s.optimization_type.value == opt_value]

        if zone_id:
            suggestions = [s for s in suggestions if s.zone_id == zone_id]

        # Sort by estimated savings (highest first)
        suggestions.sort(key=lambda s: s.estimated_savings, reverse=True)

        return [s.to_dict() for s in suggestions]
    
    def get_suggestion(self, suggestion_id: str) -> Optional[Dict[str, Any]]:
        """Return a single suggestion as dict."""
        suggestion = self._suggestions.get(suggestion_id)
        return suggestion.to_dict() if suggestion else None

    def accept_suggestion(self, suggestion_id: str) -> bool:
        """Accept an optimization suggestion."""
        if suggestion_id not in self._suggestions:
            return False

        suggestion = self._suggestions[suggestion_id]
        suggestion.accepted = True
        suggestion.rejected = False
        return True

    def reject_suggestion(self, suggestion_id: str, feedback: Optional[str] = None) -> bool:
        """Reject an optimization suggestion."""
        if suggestion_id not in self._suggestions:
            return False

        suggestion = self._suggestions[suggestion_id]
        suggestion.rejected = True
        suggestion.accepted = False
        suggestion.feedback = feedback
        return True
    
    def set_tariff_periods(self, periods: List[Dict[str, Any]]) -> None:
        """Set custom tariff periods."""
        self._tariff_periods = []

        for period_data in periods:
            period = TariffPeriod(
                name=period_data["name"],
                start_hour=period_data["start_hour"],
                end_hour=period_data["end_hour"],
                rate=period_data["rate"],
                days=period_data.get("days", ["mon", "tue", "wed", "thu", "fri"]),
            )
            self._tariff_periods.append(period)

    def get_tariff_forecast(self, hours_ahead: int = 24) -> List[Dict[str, Any]]:
        """Get tariff forecast for next N hours."""
        forecast = []
        now = datetime.now(timezone.utc)

        for i in range(hours_ahead):
            future_time = now + timedelta(hours=i)
            hour = future_time.hour
            day = future_time.strftime("%a").lower()[:3]

            tariff = self._get_tariff_for_time(hour, day)

            forecast.append({
                "hour": hour,
                "timestamp": future_time.isoformat(),
                "day": day,
                "tariff_name": tariff.name if tariff else "unknown",
                "tariff_rate": tariff.rate if tariff else 0.0,
            })

        return forecast

    def get_savings_tracking(self) -> Dict[str, Any]:
        """Summarize realized and potential savings across suggestions."""
        suggestions = list(self._suggestions.values())
        accepted = [s for s in suggestions if s.accepted]
        rejected = [s for s in suggestions if s.rejected]
        unresolved = [s for s in suggestions if not s.accepted and not s.rejected]

        def _sum(items: List[OptimizationSuggestion], unit: str) -> float:
            return round(sum(s.estimated_savings for s in items if s.estimated_savings_unit == unit), 4)

        by_type: Dict[str, int] = defaultdict(int)
        for suggestion in suggestions:
            by_type[suggestion.optimization_type.value] += 1

        return {
            "suggestion_count": len(suggestions),
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "unresolved_count": len(unresolved),
            "realized_savings_eur": _sum(accepted, "EUR"),
            "realized_savings_kwh": _sum(accepted, "kWh"),
            "potential_savings_eur": _sum(unresolved, "EUR"),
            "potential_savings_kwh": _sum(unresolved, "kWh"),
            "rejected_savings_eur": _sum(rejected, "EUR"),
            "by_type": dict(by_type),
        }

    def explain_suggestion(self, suggestion_id: str) -> Optional[Dict[str, Any]]:
        """Build a compact human/machine explanation for a suggestion."""
        suggestion = self._suggestions.get(suggestion_id)
        if not suggestion:
            return None

        action = suggestion.action_required or {}
        best_hour = action.get("best_start_hour")
        explanation = suggestion.description
        if suggestion.optimization_type == OptimizationType.SCHEDULE_SHIFT and best_hour is not None:
            explanation = (
                f"{suggestion.description}. Erwartete Ersparnis: "
                f"{suggestion.estimated_savings:.3f} {suggestion.estimated_savings_unit}. "
                f"Empfohlenes Startfenster ab {int(best_hour):02d}:00 Uhr."
            )

        return {
            "suggestion": suggestion.to_dict(),
            "explanation": explanation,
            "policy_gate_required": True,
            "recommended_action": action,
        }

    def get_report(self, zone_id: Optional[str] = None, period_hours: int = 24, budget_eur: Optional[float] = None) -> Dict[str, Any]:
        """Generate a compact optimization report for dashboards and exports."""
        summary = self.get_energy_summary(zone_id=zone_id, period_hours=period_hours)
        savings = self.get_savings_tracking()
        tariff_forecast = self.get_tariff_forecast(hours_ahead=min(max(period_hours, 1), 24))
        current_tariff = tariff_forecast[0] if tariff_forecast else None

        budget = None
        if budget_eur is not None:
            spent = round(summary["total_cost"], 4)
            remaining = round(budget_eur - spent, 4)
            utilization = round((spent / budget_eur) * 100, 2) if budget_eur > 0 else 0.0
            budget = {
                "budget_eur": budget_eur,
                "spent_eur": spent,
                "remaining_eur": remaining,
                "utilization_percent": utilization,
                "status": "over_budget" if remaining < 0 else "within_budget",
            }

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "zone_id": zone_id,
            "period_hours": period_hours,
            "summary": summary,
            "savings": savings,
            "current_tariff": current_tariff,
            "budget": budget,
            "top_suggestions": self.get_suggestions(unresolved_only=True, zone_id=zone_id)[:5],
        }


def create_energy_optimization_engine() -> EnergyOptimizationEngine:
    """Factory function to create energy optimization engine."""
    return EnergyOptimizationEngine()
