"""Smart Schedule Planner — 24h optimal device scheduling (v5.5.0).

Combines PV forecast, dynamic pricing, device baselines, and peak-shaving
to generate an optimal daily schedule for household appliances.

The planner ranks time slots by a composite score:
    slot_score = w_pv * pv_factor + w_price * price_factor + w_peak * peak_factor

Devices are then assigned to the highest-scoring slots that fit their
duration and power constraints, highest-priority devices first.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Weights for composite slot scoring
W_PV = 0.40  # Prefer high PV production
W_PRICE = 0.40  # Prefer low energy price
W_PEAK = 0.20  # Avoid concurrent high-power slots


@dataclass
class DeviceProfile:
    """Device scheduling profile."""

    device_type: str
    duration_hours: float
    consumption_kwh: float
    peak_watts: float
    priority: int = 3  # 1 = highest, 5 = lowest
    flexible: bool = True  # Can be shifted in time
    preferred_hours: list[int] | None = None  # Optional hour hints


@dataclass
class ScheduleSlot:
    """One-hour slot in the daily schedule."""

    hour: int  # 0-23
    start: str  # ISO 8601
    end: str  # ISO 8601
    pv_factor: float = 0.0  # 0-1, how much PV available
    price_eur_kwh: float = 0.30  # Default retail price
    allocated_watts: float = 0.0  # Power already allocated
    devices: list[str] = field(default_factory=list)
    score: float = 0.0  # Composite score (higher = better)


@dataclass
class DeviceSchedule:
    """Scheduled device run."""

    device_type: str
    start_hour: int
    end_hour: int
    start: str  # ISO 8601
    end: str  # ISO 8601
    estimated_cost_eur: float
    pv_coverage_percent: float  # How much of the run is covered by PV
    priority: int


@dataclass
class DailyPlan:
    """Complete 24-hour schedule plan."""

    date: str
    generated_at: str
    device_schedules: list[DeviceSchedule]
    slots: list[ScheduleSlot]
    total_estimated_cost_eur: float
    total_pv_coverage_percent: float
    peak_load_watts: float
    devices_scheduled: int
    unscheduled_devices: list[str]


# Default device profiles based on EnergyService baselines
DEFAULT_PROFILES: dict[str, DeviceProfile] = {
    "washer": DeviceProfile(
        device_type="washer",
        duration_hours=2.0,
        consumption_kwh=1.5,
        peak_watts=500,
        priority=3,
    ),
    "dryer": DeviceProfile(
        device_type="dryer",
        duration_hours=2.5,
        consumption_kwh=3.5,
        peak_watts=3000,
        priority=4,
    ),
    "dishwasher": DeviceProfile(
        device_type="dishwasher",
        duration_hours=2.0,
        consumption_kwh=1.4,
        peak_watts=1200,
        priority=3,
    ),
    "ev_charger": DeviceProfile(
        device_type="ev_charger",
        duration_hours=4.0,
        consumption_kwh=10.0,
        peak_watts=7700,
        priority=2,
    ),
    "heat_pump": DeviceProfile(
        device_type="heat_pump",
        duration_hours=8.0,
        consumption_kwh=15.0,
        peak_watts=2500,
        priority=1,
        flexible=False,
    ),
}

# Maximum simultaneous power budget (peak shaving)
MAX_CONCURRENT_WATTS = 11000.0  # ~11kW household limit


class SchedulePlanner:
    """Generate optimal 24h device schedules.

    Combines three signals into a composite slot score:
    - **PV factor**: Estimated solar production per hour (0-1)
    - **Price factor**: Inverted energy price (cheaper = higher score)
    - **Peak factor**: How much headroom remains for additional load

    Devices are assigned greedily in priority order to the
    best-scoring contiguous window that fits their duration.
    """

    def __init__(
        self,
        profiles: dict[str, DeviceProfile] | None = None,
        max_concurrent_watts: float = MAX_CONCURRENT_WATTS,
        weights: tuple[float, float, float] | None = None,
    ):
        self._profiles = profiles or dict(DEFAULT_PROFILES)
        self._max_watts = max_concurrent_watts
        self._w_pv, self._w_price, self._w_peak = weights or (W_PV, W_PRICE, W_PEAK)

    def generate_plan(
        self,
        pv_forecast: list[float] | None = None,
        price_schedule: list[dict[str, Any]] | None = None,
        off_peak_hours: list[int] | None = None,
        device_list: list[str] | None = None,
        base_date: datetime | None = None,
    ) -> DailyPlan:
        """Generate optimal daily schedule.

        Parameters
        ----------
        pv_forecast
            24 floats (one per hour), each 0.0-1.0 representing PV production factor.
            If None, a default solar curve is used.
        price_schedule
            List of ``{"start", "end", "price_eur_kwh"}`` dicts from EnergyOptimizer.
            If None, flat pricing with off-peak discount is used.
        off_peak_hours
            Hours considered off-peak (default: 0-5, 22-23).
        device_list
            Device types to schedule. If None, all profiles are used.
        base_date
            Start of the planning day. Defaults to today midnight UTC.
        """
        base = base_date or datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        off_peak = off_peak_hours or [0, 1, 2, 3, 4, 5, 22, 23]

        # Build 24 hourly slots
        slots = self._build_slots(base, pv_forecast, price_schedule, off_peak)

        # Score each slot
        self._score_slots(slots)

        # Select devices to schedule
        devices_to_schedule = self._select_devices(device_list)

        # Greedy assignment: highest priority first
        devices_to_schedule.sort(key=lambda d: d.priority)

        scheduled: list[DeviceSchedule] = []
        unscheduled: list[str] = []

        for device in devices_to_schedule:
            result = self._assign_device(device, slots)
            if result:
                scheduled.append(result)
            else:
                unscheduled.append(device.device_type)

        # Compute totals
        total_cost = sum(s.estimated_cost_eur for s in scheduled)
        total_pv = (
            sum(s.pv_coverage_percent for s in scheduled) / len(scheduled)
            if scheduled
            else 0.0
        )
        peak_load = max((s.allocated_watts for s in slots), default=0.0)

        return DailyPlan(
            date=base.date().isoformat(),
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            device_schedules=scheduled,
            slots=slots,
            total_estimated_cost_eur=round(total_cost, 4),
            total_pv_coverage_percent=round(total_pv, 1),
            peak_load_watts=round(peak_load, 0),
            devices_scheduled=len(scheduled),
            unscheduled_devices=unscheduled,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_slots(
        self,
        base: datetime,
        pv_forecast: list[float] | None,
        price_schedule: list[dict[str, Any]] | None,
        off_peak: list[int],
    ) -> list[ScheduleSlot]:
        """Build 24 hourly slots with PV and price data."""
        pv = pv_forecast or self._default_pv_curve()
        if len(pv) < 24:
            pv = pv + [0.0] * (24 - len(pv))

        price_map = self._price_map_from_schedule(price_schedule, base, off_peak)

        slots = []
        for h in range(24):
            start_dt = base + timedelta(hours=h)
            end_dt = start_dt + timedelta(hours=1)
            slots.append(
                ScheduleSlot(
                    hour=h,
                    start=start_dt.isoformat(timespec="seconds"),
                    end=end_dt.isoformat(timespec="seconds"),
                    pv_factor=max(0.0, min(1.0, pv[h])),
                    price_eur_kwh=price_map.get(h, 0.30),
                )
            )
        return slots

    def _score_slots(self, slots: list[ScheduleSlot]) -> None:
        """Compute composite score for each slot."""
        # Normalize effective price (price discounted by PV coverage):
        # strong PV availability should outweigh a merely cheap grid hour.
        effective_prices = [
            s.price_eur_kwh * (1.0 - max(0.0, min(1.0, s.pv_factor)))
            for s in slots
        ]
        p_min, p_max = min(effective_prices), max(effective_prices)
        p_range = p_max - p_min if p_max > p_min else 1.0

        for s, effective_price in zip(slots, effective_prices):
            price_factor = 1.0 - (effective_price - p_min) / p_range
            peak_factor = 1.0 - min(1.0, s.allocated_watts / self._max_watts)
            s.score = (
                self._w_pv * s.pv_factor
                + self._w_price * price_factor
                + self._w_peak * peak_factor
            )

    def _select_devices(
        self, device_list: list[str] | None
    ) -> list[DeviceProfile]:
        """Select device profiles to schedule."""
        if device_list is None:
            return list(self._profiles.values())
        return [
            self._profiles[d]
            for d in device_list
            if d in self._profiles
        ]

    def _assign_device(
        self, device: DeviceProfile, slots: list[ScheduleSlot]
    ) -> DeviceSchedule | None:
        """Find best contiguous window for a device and allocate it."""
        duration_slots = max(1, int(device.duration_hours))
        best_score = -1.0
        best_pv = -1.0
        best_start = -1

        for i in range(24 - duration_slots + 1):
            window = slots[i : i + duration_slots]

            # Check power headroom
            can_fit = all(
                (s.allocated_watts + device.peak_watts) <= self._max_watts
                for s in window
            )
            if not can_fit:
                continue

            # Check preferred hours if set
            if device.preferred_hours:
                if not any(s.hour in device.preferred_hours for s in window):
                    continue

            avg_score = sum(s.score for s in window) / len(window)
            avg_pv = sum(s.pv_factor for s in window) / len(window)
            if (
                avg_score > best_score
                or (
                    abs(avg_score - best_score) < 1e-9
                    and avg_pv > best_pv
                )
            ):
                best_score = avg_score
                best_pv = avg_pv
                best_start = i

        if best_start < 0:
            return None

        # Allocate
        window = slots[best_start : best_start + duration_slots]
        for s in window:
            s.allocated_watts += device.peak_watts
            s.devices.append(device.device_type)

        # Re-score after allocation
        self._score_slots(slots)

        # Calculate cost and PV coverage
        total_price = sum(s.price_eur_kwh for s in window)
        avg_price = total_price / len(window)
        cost = avg_price * device.consumption_kwh

        avg_pv = sum(s.pv_factor for s in window) / len(window)
        pv_coverage = avg_pv * 100.0  # PV factor as percentage

        return DeviceSchedule(
            device_type=device.device_type,
            start_hour=window[0].hour,
            end_hour=window[-1].hour + 1,
            start=window[0].start,
            end=window[-1].end,
            estimated_cost_eur=round(cost * (1.0 - avg_pv), 4),
            pv_coverage_percent=round(pv_coverage, 1),
            priority=device.priority,
        )

    @staticmethod
    def _default_pv_curve() -> list[float]:
        """Default solar production curve (Central European latitude)."""
        # Roughly models a winter/spring day with ~5kW system
        return [
            0.0,  # 0h
            0.0,  # 1h
            0.0,  # 2h
            0.0,  # 3h
            0.0,  # 4h
            0.0,  # 5h
            0.02,  # 6h (sunrise)
            0.10,  # 7h
            0.25,  # 8h
            0.45,  # 9h
            0.65,  # 10h
            0.80,  # 11h
            0.90,  # 12h (peak)
            0.85,  # 13h
            0.75,  # 14h
            0.55,  # 15h
            0.35,  # 16h
            0.15,  # 17h
            0.05,  # 18h
            0.0,  # 19h
            0.0,  # 20h
            0.0,  # 21h
            0.0,  # 22h
            0.0,  # 23h
        ]

    @staticmethod
    def _price_map_from_schedule(
        price_schedule: list[dict[str, Any]] | None,
        base: datetime,
        off_peak: list[int],
    ) -> dict[int, float]:
        """Map hours to prices from a schedule or use defaults."""
        price_map: dict[int, float] = {}

        if price_schedule:
            for slot in price_schedule:
                try:
                    start = datetime.fromisoformat(
                        slot["start"].replace("Z", "+00:00")
                    )
                    price_map[start.hour] = slot["price_eur_kwh"]
                except (ValueError, KeyError):
                    continue

        # Fill missing hours with default pricing
        for h in range(24):
            if h not in price_map:
                price_map[h] = 0.22 if h in off_peak else 0.35

        return price_map
