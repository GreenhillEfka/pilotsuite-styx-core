"""EV Charging Planner for PilotSuite (v5.25.0).

Smart EV charging scheduler combining electricity tariffs, solar
surplus, departure time constraints, and battery SoC targets.
Optimizes for cost, solar self-consumption, or fastest charge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class EVConfig:
    """Configuration for the EV and charger."""

    battery_capacity_kwh: float = 60.0
    max_charge_rate_kw: float = 11.0
    min_charge_rate_kw: float = 1.4
    current_soc_pct: float = 30.0
    target_soc_pct: float = 80.0
    charger_efficiency: float = 0.92
    connector_type: str = "type2"  # type2, ccs, chademo
    phases: int = 3  # 1 or 3 phase charging
    vehicle_name: str = "EV"


@dataclass
class DepartureSchedule:
    """Departure time constraints."""

    departure_time: str = ""  # ISO timestamp
    departure_soc_pct: float = 80.0
    recurrence: str = "none"  # none, daily, weekdays, weekends


@dataclass
class ChargingHour:
    """Single hour in the charging schedule."""

    hour: int
    timestamp: str
    action: str  # charge, solar_charge, pause, complete
    power_kw: float
    soc_start_pct: float
    soc_end_pct: float
    energy_kwh: float
    electricity_price_ct: float
    cost_ct: float
    pv_surplus_kw: float
    grid_power_kw: float
    reason: str


@dataclass
class ChargingSchedule:
    """Complete EV charging schedule."""

    hours: list[dict[str, Any]] = field(default_factory=list)
    total_energy_kwh: float = 0.0
    total_cost_eur: float = 0.0
    solar_energy_kwh: float = 0.0
    grid_energy_kwh: float = 0.0
    solar_share_pct: float = 0.0
    avg_price_ct: float = 0.0
    charge_hours: int = 0
    start_soc_pct: float = 0.0
    end_soc_pct: float = 0.0
    estimated_range_km: float = 0.0
    departure_ready: bool = True
    departure_time: str = ""
    strategy: str = "cost_optimized"
    generated_at: str = ""
    ok: bool = True


@dataclass
class EVStatus:
    """Current EV charging status."""

    vehicle_name: str = "EV"
    connector_type: str = "type2"
    current_soc_pct: float = 30.0
    target_soc_pct: float = 80.0
    current_action: str = "idle"
    current_power_kw: float = 0.0
    energy_charged_kwh: float = 0.0
    cost_so_far_eur: float = 0.0
    estimated_range_km: float = 0.0
    time_to_target_h: float = 0.0
    next_departure: str = ""
    departure_ready: bool = False
    strategy: str = "cost_optimized"
    ok: bool = True


# ── Constants ─────────────────────────────────────────────────────────────

# Average EV consumption (kWh / 100km) — varies by model
_DEFAULT_CONSUMPTION_KWH_100KM = 18.0

# Default TOU prices (ct/kWh) — German pattern
_DEFAULT_PRICES: dict[int, float] = {
    0: 22, 1: 21, 2: 20, 3: 19, 4: 20, 5: 22,
    6: 25, 7: 28, 8: 30, 9: 30, 10: 28, 11: 27,
    12: 26, 13: 27, 14: 28, 15: 29, 16: 30, 17: 32,
    18: 35, 19: 33, 20: 30, 21: 28, 22: 25, 23: 23,
}


# ── Planner ───────────────────────────────────────────────────────────────


class EVChargingPlanner:
    """Smart EV charging scheduler.

    Strategies:
    - cost_optimized: charge at cheapest hours before departure
    - solar_first: maximize PV self-consumption, fill with grid at cheap hours
    - fastest: charge at max rate immediately
    - balanced: mix of cost and solar optimization
    """

    STRATEGIES = ("cost_optimized", "solar_first", "fastest", "balanced")

    def __init__(self, config: EVConfig | None = None) -> None:
        self.config = config or EVConfig()
        self._departure = DepartureSchedule()
        self._prices: dict[int, float] = {}
        self._pv_forecast: dict[int, float] = {}
        self._strategy: str = "cost_optimized"
        self._last_schedule: ChargingSchedule | None = None
        self._energy_charged: float = 0.0
        self._cost_so_far: float = 0.0
        self._consumption_kwh_100km: float = _DEFAULT_CONSUMPTION_KWH_100KM

    # ── Data setters ──────────────────────────────────────────────────

    def set_prices(self, prices: dict[int, float]) -> None:
        """Set electricity prices {hour: ct_per_kwh}."""
        self._prices = dict(prices)

    def set_pv_forecast(self, pv: dict[int, float]) -> None:
        """Set PV surplus forecast {hour: kw}."""
        self._pv_forecast = dict(pv)

    def set_strategy(self, strategy: str) -> None:
        """Set charging strategy."""
        if strategy in self.STRATEGIES:
            self._strategy = strategy

    def set_departure(
        self,
        departure_time: str,
        departure_soc_pct: float = 80.0,
        recurrence: str = "none",
    ) -> None:
        """Set departure schedule."""
        self._departure = DepartureSchedule(
            departure_time=departure_time,
            departure_soc_pct=departure_soc_pct,
            recurrence=recurrence,
        )

    def set_soc(self, soc_pct: float) -> None:
        """Update current state of charge."""
        self.config.current_soc_pct = max(0.0, min(soc_pct, 100.0))

    def update_config(self, **kwargs: Any) -> None:
        """Update configuration parameters."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    def set_consumption(self, kwh_per_100km: float) -> None:
        """Set vehicle consumption for range estimation."""
        self._consumption_kwh_100km = max(5.0, min(kwh_per_100km, 40.0))

    def import_tariff_data(self, prices: list[dict[str, Any]]) -> None:
        """Import from tariff engine format."""
        self._prices = {}
        for p in prices:
            hr = p.get("hour", 0)
            price = p.get("price_ct", p.get("price", 30.0))
            self._prices[hr] = float(price)

    # ── Helpers ───────────────────────────────────────────────────────

    def _energy_needed_kwh(self) -> float:
        """Calculate energy needed to reach target SoC."""
        soc_delta = self.config.target_soc_pct - self.config.current_soc_pct
        if soc_delta <= 0:
            return 0.0
        return (soc_delta / 100.0) * self.config.battery_capacity_kwh / self.config.charger_efficiency

    def _departure_energy_needed_kwh(self) -> float:
        """Energy needed to reach departure SoC target."""
        soc_delta = self._departure.departure_soc_pct - self.config.current_soc_pct
        if soc_delta <= 0:
            return 0.0
        return (soc_delta / 100.0) * self.config.battery_capacity_kwh / self.config.charger_efficiency

    def _hours_until_departure(self) -> int | None:
        """Calculate hours until departure."""
        if not self._departure.departure_time:
            return None
        try:
            dep = datetime.fromisoformat(self._departure.departure_time)
            now = datetime.now(timezone.utc)
            if dep.tzinfo is None:
                dep = dep.replace(tzinfo=timezone.utc)
            delta = (dep - now).total_seconds() / 3600
            return max(0, int(delta))
        except (ValueError, TypeError):
            return None

    def _soc_for_energy(self, energy_kwh: float) -> float:
        """Convert energy to SoC percentage gain."""
        effective = energy_kwh * self.config.charger_efficiency
        return (effective / self.config.battery_capacity_kwh) * 100.0

    def _estimated_range_km(self, soc_pct: float) -> float:
        """Estimate range from SoC."""
        usable_kwh = (soc_pct / 100.0) * self.config.battery_capacity_kwh
        return (usable_kwh / self._consumption_kwh_100km) * 100.0

    # ── Schedule optimization ─────────────────────────────────────────

    def optimize(self, horizon_hours: int = 48) -> ChargingSchedule:
        """Generate optimized EV charging schedule.

        Algorithm:
        1. Calculate total energy needed
        2. Determine available hours (constrained by departure if set)
        3. Rank hours by strategy (price, solar, speed)
        4. Allocate charging to preferred hours
        5. Forward simulation tracking SoC
        """
        now = datetime.now(timezone.utc)
        energy_needed = self._energy_needed_kwh()
        hours_to_dep = self._hours_until_departure()

        # Effective horizon is minimum of requested and departure
        effective_horizon = horizon_hours
        if hours_to_dep is not None:
            effective_horizon = min(horizon_hours, hours_to_dep)

        # Calculate how many hours of charging needed
        hours_needed = 0
        if energy_needed > 0:
            hours_needed = max(1, int(
                energy_needed / self.config.max_charge_rate_kw + 0.99
            ))

        # Build hour data with prices and PV
        hour_data = []
        for h in range(horizon_hours):
            hour_of_day = h % 24
            price = self._prices.get(h, self._prices.get(
                hour_of_day, _DEFAULT_PRICES.get(hour_of_day, 30.0)
            ))
            pv = self._pv_forecast.get(h, self._pv_forecast.get(hour_of_day, 0.0))
            hour_data.append({
                "h": h,
                "price": price,
                "pv": pv,
                "within_deadline": h < effective_horizon,
            })

        # Rank hours by strategy
        if self._strategy == "cost_optimized":
            # Cheapest hours first, prefer within deadline
            ranked = sorted(
                hour_data,
                key=lambda x: (not x["within_deadline"], x["price"]),
            )
        elif self._strategy == "solar_first":
            # Highest PV surplus first, then cheapest grid
            ranked = sorted(
                hour_data,
                key=lambda x: (not x["within_deadline"], -x["pv"], x["price"]),
            )
        elif self._strategy == "fastest":
            # Just charge ASAP — first hours first
            ranked = sorted(hour_data, key=lambda x: x["h"])
        else:
            # balanced — weighted score of price and solar
            ranked = sorted(
                hour_data,
                key=lambda x: (
                    not x["within_deadline"],
                    x["price"] - x["pv"] * 5,  # bonus for solar
                ),
            )

        # Select hours to charge
        charge_hours: set[int] = set()
        energy_allocated = 0.0
        for entry in ranked:
            if energy_allocated >= energy_needed:
                break
            charge_hours.add(entry["h"])
            energy_allocated += self.config.max_charge_rate_kw

        # Forward simulation
        soc = self.config.current_soc_pct
        start_soc = soc
        schedule_hours: list[ChargingHour] = []
        total_energy = 0.0
        total_cost = 0.0
        solar_energy = 0.0
        grid_energy = 0.0
        charge_count = 0

        for h in range(horizon_hours):
            hour_of_day = h % 24
            ts = (now + timedelta(hours=h)).isoformat()
            price = self._prices.get(h, self._prices.get(
                hour_of_day, _DEFAULT_PRICES.get(hour_of_day, 30.0)
            ))
            pv = self._pv_forecast.get(h, self._pv_forecast.get(hour_of_day, 0.0))

            if soc >= self.config.target_soc_pct:
                # Target reached
                schedule_hours.append(ChargingHour(
                    hour=h, timestamp=ts, action="complete",
                    power_kw=0, soc_start_pct=round(soc, 1),
                    soc_end_pct=round(soc, 1), energy_kwh=0,
                    electricity_price_ct=round(price, 1), cost_ct=0,
                    pv_surplus_kw=round(pv, 2), grid_power_kw=0,
                    reason="Target SoC reached",
                ))
                continue

            if h in charge_hours:
                # Charge this hour
                power = self.config.max_charge_rate_kw
                energy_this_hour = power  # kWh in 1 hour

                # Limit to what's needed
                remaining_kwh = self._energy_needed_for_soc(soc, self.config.target_soc_pct)
                energy_this_hour = min(energy_this_hour, remaining_kwh)
                power = energy_this_hour

                # Split into solar and grid
                pv_used = min(pv, power)
                grid_used = max(0, power - pv_used)

                cost = grid_used * price  # solar portion is free
                soc_gain = self._soc_for_energy(energy_this_hour)
                new_soc = min(soc + soc_gain, 100.0)

                action = "solar_charge" if pv_used > grid_used else "charge"
                reason = f"{'Solar' if action == 'solar_charge' else 'Grid'} charge @ {price:.0f} ct/kWh"

                schedule_hours.append(ChargingHour(
                    hour=h, timestamp=ts, action=action,
                    power_kw=round(power, 2),
                    soc_start_pct=round(soc, 1),
                    soc_end_pct=round(new_soc, 1),
                    energy_kwh=round(energy_this_hour, 2),
                    electricity_price_ct=round(price, 1),
                    cost_ct=round(cost, 1),
                    pv_surplus_kw=round(pv, 2),
                    grid_power_kw=round(grid_used, 2),
                    reason=reason,
                ))

                total_energy += energy_this_hour
                total_cost += cost
                solar_energy += pv_used
                grid_energy += grid_used
                charge_count += 1
                soc = new_soc
            else:
                # Pause
                schedule_hours.append(ChargingHour(
                    hour=h, timestamp=ts, action="pause",
                    power_kw=0, soc_start_pct=round(soc, 1),
                    soc_end_pct=round(soc, 1), energy_kwh=0,
                    electricity_price_ct=round(price, 1), cost_ct=0,
                    pv_surplus_kw=round(pv, 2), grid_power_kw=0,
                    reason="Waiting for better rate" if self._strategy != "fastest" else "Idle",
                ))

        # Check departure readiness
        departure_ready = True
        if hours_to_dep is not None and self._departure.departure_soc_pct > 0:
            # Check SoC at departure time
            dep_soc = start_soc
            for sh in schedule_hours[:effective_horizon]:
                dep_soc = sh.soc_end_pct if isinstance(sh, ChargingHour) else sh.get("soc_end_pct", dep_soc)
            if isinstance(dep_soc, (int, float)):
                departure_ready = dep_soc >= self._departure.departure_soc_pct

        avg_price = total_cost / total_energy if total_energy > 0 else 0.0
        solar_share = (solar_energy / total_energy * 100) if total_energy > 0 else 0.0

        schedule = ChargingSchedule(
            hours=[self._hour_to_dict(h) for h in schedule_hours],
            total_energy_kwh=round(total_energy, 2),
            total_cost_eur=round(total_cost / 100, 2),
            solar_energy_kwh=round(solar_energy, 2),
            grid_energy_kwh=round(grid_energy, 2),
            solar_share_pct=round(solar_share, 1),
            avg_price_ct=round(avg_price, 1),
            charge_hours=charge_count,
            start_soc_pct=round(start_soc, 1),
            end_soc_pct=round(soc, 1),
            estimated_range_km=round(self._estimated_range_km(soc), 0),
            departure_ready=departure_ready,
            departure_time=self._departure.departure_time,
            strategy=self._strategy,
            generated_at=now.isoformat(),
        )

        self._last_schedule = schedule
        return schedule

    def _energy_needed_for_soc(self, current_soc: float, target_soc: float) -> float:
        """Energy needed to go from current to target SoC."""
        delta = target_soc - current_soc
        if delta <= 0:
            return 0.0
        return (delta / 100.0) * self.config.battery_capacity_kwh / self.config.charger_efficiency

    def get_status(self) -> EVStatus:
        """Get current EV charging status."""
        current_action = "idle"
        current_power = 0.0

        if self._last_schedule and self._last_schedule.hours:
            for h in self._last_schedule.hours:
                if h.get("action") in ("charge", "solar_charge"):
                    current_action = h["action"]
                    current_power = h.get("power_kw", 0)
                    break

        energy_needed = self._energy_needed_kwh()
        time_to_target = energy_needed / self.config.max_charge_rate_kw if energy_needed > 0 else 0.0

        return EVStatus(
            vehicle_name=self.config.vehicle_name,
            connector_type=self.config.connector_type,
            current_soc_pct=round(self.config.current_soc_pct, 1),
            target_soc_pct=self.config.target_soc_pct,
            current_action=current_action,
            current_power_kw=round(current_power, 2),
            energy_charged_kwh=round(self._energy_charged, 2),
            cost_so_far_eur=round(self._cost_so_far / 100, 2),
            estimated_range_km=round(
                self._estimated_range_km(self.config.current_soc_pct), 0
            ),
            time_to_target_h=round(time_to_target, 1),
            next_departure=self._departure.departure_time,
            departure_ready=self.config.current_soc_pct >= self._departure.departure_soc_pct
            if self._departure.departure_time
            else True,
            strategy=self._strategy,
        )

    @staticmethod
    def _hour_to_dict(h: ChargingHour) -> dict[str, Any]:
        return {
            "hour": h.hour,
            "timestamp": h.timestamp,
            "action": h.action,
            "power_kw": h.power_kw,
            "soc_start_pct": h.soc_start_pct,
            "soc_end_pct": h.soc_end_pct,
            "energy_kwh": h.energy_kwh,
            "electricity_price_ct": h.electricity_price_ct,
            "cost_ct": h.cost_ct,
            "pv_surplus_kw": h.pv_surplus_kw,
            "grid_power_kw": h.grid_power_kw,
            "reason": h.reason,
        }
