"""Battery Strategy Optimizer (v5.23.0).

ML-based charge/discharge scheduling that combines:
- Electricity price forecasts (buy low, sell high)
- PV production forecasts (charge from solar)
- Consumption patterns (predict demand)
- Battery degradation model (minimize cycles)

Outputs hourly charge/discharge schedule for the next 24-48h.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────


@dataclass
class BatteryConfig:
    """Battery system configuration."""

    capacity_kwh: float = 10.0
    max_charge_kw: float = 5.0
    max_discharge_kw: float = 5.0
    min_soc_pct: float = 10.0  # minimum state of charge
    max_soc_pct: float = 95.0
    current_soc_pct: float = 50.0
    round_trip_efficiency: float = 0.92  # AC-to-AC
    max_cycles_per_day: float = 2.0
    degradation_cost_per_kwh: float = 0.05  # EUR/kWh cycled


@dataclass
class ScheduleHour:
    """Single hour in the battery schedule."""

    hour: int  # 0-47
    timestamp: str
    action: str  # "charge", "discharge", "hold", "charge_solar"
    power_kw: float  # positive = charge, negative = discharge
    soc_start_pct: float
    soc_end_pct: float
    price_ct_kwh: float
    pv_available_kw: float
    expected_consumption_kw: float
    savings_eur: float
    reason: str


@dataclass
class BatterySchedule:
    """Complete battery optimization schedule."""

    hours: list[dict]
    total_hours: int
    total_charge_kwh: float
    total_discharge_kwh: float
    total_solar_charge_kwh: float
    total_grid_charge_kwh: float
    estimated_savings_eur: float
    estimated_cycles: float
    avg_charge_price_ct: float
    avg_discharge_price_ct: float
    strategy: str  # "arbitrage", "solar_first", "peak_shaving", "backup"
    generated_at: str


@dataclass
class BatteryStatus:
    """Current battery status."""

    soc_pct: float
    soc_kwh: float
    capacity_kwh: float
    current_action: str
    current_power_kw: float
    cycles_today: float
    next_charge_at: str
    next_discharge_at: str
    strategy: str
    health_pct: float


# ── Main Optimizer ───────────────────────────────────────────────────────


class BatteryStrategyOptimizer:
    """Optimizes battery charge/discharge scheduling.

    Uses a greedy algorithm with look-ahead scoring:
    1. Score each hour by price differential potential
    2. Prioritize solar charging (free energy)
    3. Apply charge during cheapest hours
    4. Discharge during most expensive hours
    5. Respect SoC limits and degradation budget
    """

    def __init__(self, config: BatteryConfig | None = None):
        self._config = config or BatteryConfig()
        self._hourly_prices: dict[int, float] = {}
        self._hourly_pv: dict[int, float] = {}
        self._hourly_consumption: dict[int, float] = {}
        self._cycles_today: float = 0.0
        self._last_schedule: BatterySchedule | None = None

    @property
    def config(self) -> BatteryConfig:
        return self._config

    def update_config(self, **kwargs) -> None:
        """Update battery configuration."""
        for k, v in kwargs.items():
            if hasattr(self._config, k) and v is not None:
                setattr(self._config, k, float(v))

    def set_soc(self, soc_pct: float) -> None:
        """Update current state of charge."""
        self._config.current_soc_pct = max(0, min(100, soc_pct))

    def set_prices(self, prices: dict[int, float]) -> None:
        """Set hourly electricity prices (hour -> ct/kWh)."""
        self._hourly_prices = prices

    def set_pv_forecast(self, pv: dict[int, float]) -> None:
        """Set hourly PV production forecast (hour -> kW)."""
        self._hourly_pv = pv

    def set_consumption_forecast(self, consumption: dict[int, float]) -> None:
        """Set hourly consumption forecast (hour -> kW)."""
        self._hourly_consumption = consumption

    def import_forecast_data(self, forecast_hours: list[dict]) -> None:
        """Import data from EnergyForecastEngine output."""
        for h in forecast_hours:
            hour = h.get("hour", 0)
            self._hourly_prices[hour] = h.get("price_ct_kwh", 30.0)
            self._hourly_pv[hour] = h.get("pv_kw_estimated", 0.0)

    def _default_price(self, hour_of_day: int) -> float:
        """Default TOU price for an hour of day."""
        if 0 <= hour_of_day <= 5:
            return 22.0
        elif 6 <= hour_of_day <= 9:
            return 32.0
        elif 10 <= hour_of_day <= 16:
            return 28.0
        elif 17 <= hour_of_day <= 20:
            return 35.0
        else:
            return 25.0

    def _default_consumption(self, hour_of_day: int) -> float:
        """Default household consumption pattern (kW)."""
        if 0 <= hour_of_day <= 5:
            return 0.3
        elif 6 <= hour_of_day <= 8:
            return 1.2
        elif 9 <= hour_of_day <= 11:
            return 0.8
        elif 12 <= hour_of_day <= 13:
            return 1.5
        elif 14 <= hour_of_day <= 16:
            return 0.6
        elif 17 <= hour_of_day <= 20:
            return 2.0
        elif 21 <= hour_of_day <= 23:
            return 1.0
        return 0.5

    def _soc_to_kwh(self, soc_pct: float) -> float:
        return soc_pct / 100.0 * self._config.capacity_kwh

    def _kwh_to_soc(self, kwh: float) -> float:
        return kwh / self._config.capacity_kwh * 100.0

    def optimize(self, horizon_hours: int = 48) -> BatterySchedule:
        """Generate optimal charge/discharge schedule.

        Strategy:
        1. Identify cheap hours (buy) and expensive hours (sell)
        2. Solar hours always get priority for charging
        3. Respect SoC constraints and cycle budget
        4. Calculate savings vs no-battery baseline
        """
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        cfg = self._config
        schedule: list[ScheduleHour] = []

        # Get prices and classify hours
        prices = {}
        pv = {}
        consumption = {}
        for h in range(horizon_hours):
            dt = now + timedelta(hours=h)
            hod = dt.hour
            prices[h] = self._hourly_prices.get(h, self._default_price(hod))
            pv[h] = self._hourly_pv.get(h, 0.0)
            consumption[h] = self._hourly_consumption.get(h, self._default_consumption(hod))

        # Calculate price statistics
        all_prices = list(prices.values())
        avg_price = sum(all_prices) / len(all_prices)
        price_sorted = sorted(range(horizon_hours), key=lambda h: prices[h])

        # Identify cheap/expensive quartiles
        q1_idx = horizon_hours // 4
        cheap_hours = set(price_sorted[:q1_idx])
        expensive_hours = set(price_sorted[-q1_idx:])

        # Simulate battery over horizon
        current_soc = cfg.current_soc_pct
        soc_kwh = self._soc_to_kwh(current_soc)
        total_charge = 0.0
        total_discharge = 0.0
        total_solar_charge = 0.0
        total_grid_charge = 0.0
        total_savings = 0.0
        cycle_kwh = 0.0
        max_cycle_kwh = cfg.max_cycles_per_day * cfg.capacity_kwh * (horizon_hours / 24.0)
        charge_prices = []
        discharge_prices = []

        for h in range(horizon_hours):
            dt = now + timedelta(hours=h)
            price = prices[h]
            pv_kw = pv[h]
            cons_kw = consumption[h]
            soc_start = current_soc

            # Net PV available after consumption
            net_pv = max(0, pv_kw - cons_kw)
            action = "hold"
            power_kw = 0.0
            reason = "Default hold"
            savings = 0.0

            # Decision logic
            usable_kwh = self._soc_to_kwh(current_soc - cfg.min_soc_pct)
            headroom_kwh = self._soc_to_kwh(cfg.max_soc_pct - current_soc)

            if cycle_kwh >= max_cycle_kwh:
                # Cycle budget exhausted
                action = "hold"
                reason = "Zyklusbudget erschoepft"

            elif net_pv > 0.5 and headroom_kwh > 0.1:
                # Priority 1: Charge from solar (free)
                charge_kw = min(net_pv, cfg.max_charge_kw, headroom_kwh)
                charge_kwh_eff = charge_kw * math.sqrt(cfg.round_trip_efficiency)
                soc_kwh += charge_kwh_eff
                current_soc = self._kwh_to_soc(soc_kwh)
                action = "charge_solar"
                power_kw = round(charge_kw, 2)
                total_solar_charge += charge_kw
                total_charge += charge_kw
                cycle_kwh += charge_kw
                savings = charge_kw * price / 100.0  # saved vs buying from grid
                reason = f"Solar laden: {net_pv:.1f}kW verfuegbar"

            elif h in cheap_hours and headroom_kwh > 0.5 and price < avg_price * 0.85:
                # Priority 2: Charge from grid at cheap hours
                charge_kw = min(cfg.max_charge_kw, headroom_kwh)
                charge_kwh_eff = charge_kw * math.sqrt(cfg.round_trip_efficiency)
                soc_kwh += charge_kwh_eff
                current_soc = self._kwh_to_soc(soc_kwh)
                action = "charge"
                power_kw = round(charge_kw, 2)
                total_grid_charge += charge_kw
                total_charge += charge_kw
                cycle_kwh += charge_kw
                charge_prices.append(price)
                # Savings calculated later when discharged at higher price
                reason = f"Guenstig laden: {price:.1f} ct/kWh"

            elif h in expensive_hours and usable_kwh > 0.5 and price > avg_price * 1.15:
                # Priority 3: Discharge at expensive hours
                discharge_kw = min(cfg.max_discharge_kw, usable_kwh, cons_kw + 1.0)
                discharge_kwh_eff = discharge_kw * math.sqrt(cfg.round_trip_efficiency)
                soc_kwh -= discharge_kw  # raw discharge
                current_soc = self._kwh_to_soc(soc_kwh)
                action = "discharge"
                power_kw = round(-discharge_kw, 2)
                total_discharge += discharge_kw
                cycle_kwh += discharge_kw
                discharge_prices.append(price)
                # Savings: sell at current price minus avg charge price
                avg_charge = sum(charge_prices) / len(charge_prices) if charge_prices else avg_price
                savings = discharge_kwh_eff * (price - avg_charge) / 100.0
                savings -= cfg.degradation_cost_per_kwh * discharge_kw
                reason = f"Teuer entladen: {price:.1f} ct/kWh"

            else:
                action = "hold"
                reason = "Halten — kein vorteilhafter Zeitpunkt"

            # Clamp SoC
            current_soc = max(cfg.min_soc_pct, min(cfg.max_soc_pct, current_soc))
            soc_kwh = self._soc_to_kwh(current_soc)
            total_savings += max(0, savings)

            schedule.append(ScheduleHour(
                hour=h,
                timestamp=dt.isoformat(),
                action=action,
                power_kw=power_kw,
                soc_start_pct=round(soc_start, 1),
                soc_end_pct=round(current_soc, 1),
                price_ct_kwh=round(price, 2),
                pv_available_kw=round(pv_kw, 2),
                expected_consumption_kw=round(cons_kw, 2),
                savings_eur=round(savings, 3),
                reason=reason,
            ))

        # Determine dominant strategy
        if total_solar_charge > total_grid_charge:
            strategy = "solar_first"
        elif total_discharge > 0 and charge_prices and discharge_prices:
            strategy = "arbitrage"
        elif total_discharge > total_charge:
            strategy = "peak_shaving"
        else:
            strategy = "backup"

        estimated_cycles = cycle_kwh / (2 * cfg.capacity_kwh) if cfg.capacity_kwh > 0 else 0

        result = BatterySchedule(
            hours=[asdict(s) for s in schedule],
            total_hours=len(schedule),
            total_charge_kwh=round(total_charge, 2),
            total_discharge_kwh=round(total_discharge, 2),
            total_solar_charge_kwh=round(total_solar_charge, 2),
            total_grid_charge_kwh=round(total_grid_charge, 2),
            estimated_savings_eur=round(total_savings, 2),
            estimated_cycles=round(estimated_cycles, 2),
            avg_charge_price_ct=round(
                sum(charge_prices) / len(charge_prices) if charge_prices else 0, 2
            ),
            avg_discharge_price_ct=round(
                sum(discharge_prices) / len(discharge_prices) if discharge_prices else 0, 2
            ),
            strategy=strategy,
            generated_at=datetime.now().isoformat(),
        )
        self._last_schedule = result
        return result

    def get_status(self) -> BatteryStatus:
        """Get current battery status summary."""
        cfg = self._config

        # Find next charge/discharge from schedule
        next_charge = ""
        next_discharge = ""
        current_action = "hold"
        current_power = 0.0

        if self._last_schedule:
            for h in self._last_schedule.hours:
                if h.get("hour") == 0:
                    current_action = h.get("action", "hold")
                    current_power = h.get("power_kw", 0)
                if not next_charge and h.get("action") in ("charge", "charge_solar"):
                    next_charge = h.get("timestamp", "")
                if not next_discharge and h.get("action") == "discharge":
                    next_discharge = h.get("timestamp", "")

        return BatteryStatus(
            soc_pct=round(cfg.current_soc_pct, 1),
            soc_kwh=round(self._soc_to_kwh(cfg.current_soc_pct), 2),
            capacity_kwh=cfg.capacity_kwh,
            current_action=current_action,
            current_power_kw=current_power,
            cycles_today=round(self._cycles_today, 2),
            next_charge_at=next_charge,
            next_discharge_at=next_discharge,
            strategy=self._last_schedule.strategy if self._last_schedule else "none",
            health_pct=100.0,  # placeholder for degradation model
        )
