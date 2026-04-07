"""Heat Pump Controller for PilotSuite (v5.24.0).

COP-optimized scheduling for heat pumps using weather forecasts and
electricity tariffs. Determines the most cost-efficient operating
hours while maintaining comfort targets.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Heat pump types ───────────────────────────────────────────────────────

PUMP_TYPES = ("air_water", "ground_water", "air_air")

# Carnot efficiency factor by pump type (fraction of ideal Carnot COP)
_CARNOT_ETA = {
    "air_water": 0.45,
    "ground_water": 0.55,
    "air_air": 0.40,
}

# Ground temperature assumption for ground-source pumps (°C)
_GROUND_TEMP_C = 10.0


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass
class HeatPumpConfig:
    """Configuration for the heat pump system."""

    pump_type: str = "air_water"
    nominal_power_kw: float = 8.0
    max_flow_temp_c: float = 55.0
    min_outdoor_temp_c: float = -20.0
    target_room_temp_c: float = 21.0
    building_thermal_mass_kwh_per_k: float = 2.5
    hot_water_tank_l: float = 300.0
    hot_water_target_c: float = 55.0
    hot_water_min_c: float = 45.0
    current_room_temp_c: float = 21.0
    current_hot_water_temp_c: float = 50.0
    defrost_threshold_c: float = 3.0
    max_runtime_hours_per_day: int = 18


@dataclass
class HeatPumpHour:
    """Single hour in the heat pump schedule."""

    hour: int
    timestamp: str
    action: str  # heat, dhw, off, defrost, solar_boost
    power_kw: float
    cop: float
    outdoor_temp_c: float
    electricity_price_ct: float
    cost_ct: float
    heat_delivered_kwh: float
    room_temp_c: float
    hot_water_temp_c: float
    pv_surplus_kw: float
    reason: str


@dataclass
class HeatPumpSchedule:
    """Complete heat pump schedule."""

    hours: list[dict[str, Any]] = field(default_factory=list)
    total_heat_kwh: float = 0.0
    total_electricity_kwh: float = 0.0
    total_cost_eur: float = 0.0
    avg_cop: float = 0.0
    best_cop_hour: int = 0
    worst_cop_hour: int = 0
    dhw_cycles: int = 0
    defrost_hours: int = 0
    runtime_hours: int = 0
    strategy: str = "cop_optimized"
    generated_at: str = ""
    ok: bool = True


@dataclass
class HeatPumpStatus:
    """Current heat pump status summary."""

    pump_type: str = "air_water"
    current_action: str = "off"
    current_cop: float = 0.0
    current_power_kw: float = 0.0
    room_temp_c: float = 21.0
    target_room_temp_c: float = 21.0
    hot_water_temp_c: float = 50.0
    hot_water_target_c: float = 55.0
    outdoor_temp_c: float = 10.0
    runtime_today_h: float = 0.0
    heat_today_kwh: float = 0.0
    electricity_today_kwh: float = 0.0
    cost_today_eur: float = 0.0
    avg_cop_today: float = 0.0
    strategy: str = "cop_optimized"
    next_action: str = ""
    next_action_at: str = ""
    ok: bool = True


# ── COP calculation ───────────────────────────────────────────────────────


def calculate_cop(
    pump_type: str,
    outdoor_temp_c: float,
    flow_temp_c: float,
) -> float:
    """Calculate COP using simplified Carnot model.

    COP = eta_carnot * T_hot_K / (T_hot_K - T_cold_K)
    where T_cold is outdoor temp (air-source) or ground temp (ground-source).
    """
    eta = _CARNOT_ETA.get(pump_type, 0.45)

    if pump_type == "ground_water":
        t_cold = _GROUND_TEMP_C
    else:
        t_cold = outdoor_temp_c

    t_hot_k = flow_temp_c + 273.15
    t_cold_k = t_cold + 273.15

    delta = t_hot_k - t_cold_k
    if delta <= 0:
        return 6.0  # cap at very high COP

    cop = eta * t_hot_k / delta

    # Clamp to realistic range
    return max(1.0, min(cop, 7.0))


def needs_defrost(outdoor_temp_c: float, threshold_c: float = 3.0) -> bool:
    """Check if defrost cycle is likely needed (air-source pumps)."""
    return -2.0 <= outdoor_temp_c <= threshold_c


# ── Default profiles ──────────────────────────────────────────────────────

# Typical German outdoor temperature profile for a winter day (°C)
_DEFAULT_OUTDOOR_TEMPS: dict[int, float] = {
    0: 0.5, 1: 0.0, 2: -0.5, 3: -1.0, 4: -1.5, 5: -1.0,
    6: -0.5, 7: 0.0, 8: 1.0, 9: 2.5, 10: 4.0, 11: 5.5,
    12: 6.5, 13: 7.0, 14: 7.0, 15: 6.5, 16: 5.5, 17: 4.0,
    18: 3.0, 19: 2.0, 20: 1.5, 21: 1.0, 22: 0.8, 23: 0.5,
}

# Default electricity prices (ct/kWh) — German TOU pattern
_DEFAULT_PRICES: dict[int, float] = {
    0: 22, 1: 21, 2: 20, 3: 19, 4: 20, 5: 22,
    6: 25, 7: 28, 8: 30, 9: 30, 10: 28, 11: 27,
    12: 26, 13: 27, 14: 28, 15: 29, 16: 30, 17: 32,
    18: 35, 19: 33, 20: 30, 21: 28, 22: 25, 23: 23,
}


# ── Controller ────────────────────────────────────────────────────────────


class HeatPumpController:
    """COP-optimized heat pump scheduling controller.

    Combines weather forecasts, electricity tariffs, PV surplus, and
    building thermal mass to compute optimal operating schedules.

    Strategies:
    - cop_optimized: balance COP and price for lowest cost per kWh heat
    - price_optimized: run at cheapest electricity hours
    - comfort_first: keep room temp stable regardless of cost
    - solar_boost: maximize PV self-consumption
    """

    STRATEGIES = ("cop_optimized", "price_optimized", "comfort_first", "solar_boost")

    def __init__(self, config: HeatPumpConfig | None = None) -> None:
        self.config = config or HeatPumpConfig()
        self._outdoor_temps: dict[int, float] = {}
        self._prices: dict[int, float] = {}
        self._pv_forecast: dict[int, float] = {}
        self._strategy: str = "cop_optimized"
        self._last_schedule: HeatPumpSchedule | None = None
        self._runtime_today: float = 0.0
        self._heat_today: float = 0.0
        self._electricity_today: float = 0.0
        self._cost_today: float = 0.0

    # ── Data setters ──────────────────────────────────────────────────

    def set_outdoor_temps(self, temps: dict[int, float]) -> None:
        """Set outdoor temperature forecast {hour: temp_c}."""
        self._outdoor_temps = dict(temps)

    def set_prices(self, prices: dict[int, float]) -> None:
        """Set electricity prices {hour: ct_per_kwh}."""
        self._prices = dict(prices)

    def set_pv_forecast(self, pv: dict[int, float]) -> None:
        """Set PV surplus forecast {hour: kw}."""
        self._pv_forecast = dict(pv)

    def set_strategy(self, strategy: str) -> None:
        """Set scheduling strategy."""
        if strategy in self.STRATEGIES:
            self._strategy = strategy

    def update_config(self, **kwargs: Any) -> None:
        """Update configuration parameters."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    def set_room_temp(self, temp_c: float) -> None:
        """Update current room temperature."""
        self.config.current_room_temp_c = max(5.0, min(temp_c, 35.0))

    def set_hot_water_temp(self, temp_c: float) -> None:
        """Update current hot water temperature."""
        self.config.current_hot_water_temp_c = max(10.0, min(temp_c, 70.0))

    def import_weather_data(self, hours: list[dict[str, Any]]) -> None:
        """Import weather data from forecast engine format.

        Expected: [{"hour": 0, "temperature_c": 5.0}, ...]
        """
        self._outdoor_temps = {}
        for h in hours:
            hr = h.get("hour", 0)
            temp = h.get("temperature_c", h.get("temp_c", 10.0))
            self._outdoor_temps[hr] = float(temp)

    def import_tariff_data(self, prices: list[dict[str, Any]]) -> None:
        """Import prices from tariff engine format.

        Expected: [{"hour": 0, "price_ct": 25.0}, ...]
        """
        self._prices = {}
        for p in prices:
            hr = p.get("hour", 0)
            price = p.get("price_ct", p.get("price", 30.0))
            self._prices[hr] = float(price)

    # ── COP helpers ───────────────────────────────────────────────────

    def get_cop(self, outdoor_temp_c: float) -> float:
        """Get COP for current config and outdoor temperature."""
        return calculate_cop(
            self.config.pump_type,
            outdoor_temp_c,
            self.config.max_flow_temp_c,
        )

    def get_effective_cost(self, hour: int) -> float:
        """Get effective cost per kWh of heat at given hour.

        effective_cost = electricity_price / COP
        """
        price = self._prices.get(hour % 24, _DEFAULT_PRICES.get(hour % 24, 30))
        temp = self._outdoor_temps.get(hour % 24, _DEFAULT_OUTDOOR_TEMPS.get(hour % 24, 5))
        cop = self.get_cop(temp)
        return price / cop

    # ── Thermal model ─────────────────────────────────────────────────

    def _heat_loss_kw(self, room_temp_c: float, outdoor_temp_c: float) -> float:
        """Estimate building heat loss (kW).

        Simple model: Q_loss = UA * (T_room - T_outdoor)
        UA is derived from thermal mass and typical insulation.
        """
        delta_t = room_temp_c - outdoor_temp_c
        if delta_t <= 0:
            return 0.0
        # Typical UA ~0.15 kW/K for a well-insulated German home
        ua = self.config.building_thermal_mass_kwh_per_k * 0.06
        return ua * delta_t

    def _room_temp_after_hour(
        self, current_temp_c: float, outdoor_temp_c: float, heat_input_kwh: float
    ) -> float:
        """Calculate room temp after 1 hour given heat input."""
        loss = self._heat_loss_kw(current_temp_c, outdoor_temp_c)
        net_heat = heat_input_kwh - loss
        delta_t = net_heat / max(self.config.building_thermal_mass_kwh_per_k, 0.5)
        return current_temp_c + delta_t

    def _dhw_heat_needed_kwh(self) -> float:
        """Heat needed to bring hot water to target (kWh)."""
        delta_t = self.config.hot_water_target_c - self.config.current_hot_water_temp_c
        if delta_t <= 0:
            return 0.0
        # Q = m * cp * dT; water cp ≈ 1.16 Wh/(kg·K); 1L ≈ 1kg
        return (self.config.hot_water_tank_l * 1.16 * delta_t) / 1000.0

    # ── Schedule optimization ─────────────────────────────────────────

    def optimize(self, horizon_hours: int = 48) -> HeatPumpSchedule:
        """Generate optimized heat pump schedule.

        Algorithm:
        1. Calculate COP and effective cost for each hour
        2. Determine heating demand from thermal model
        3. Score and rank hours by strategy
        4. Assign actions (heat, dhw, defrost, solar_boost, off)
        5. Simulate forward to track room/water temperatures
        """
        now = datetime.now(timezone.utc)
        hours_data: list[HeatPumpHour] = []

        room_temp = self.config.current_room_temp_c
        hw_temp = self.config.current_hot_water_temp_c
        runtime = 0
        total_heat = 0.0
        total_elec = 0.0
        total_cost = 0.0
        dhw_cycles = 0
        defrost_hours = 0
        best_cop = (0, 0.0)
        worst_cop = (0, 99.0)

        # Pre-compute scores for ranking
        scored_hours = []
        for h in range(horizon_hours):
            hour_of_day = h % 24
            outdoor = self._outdoor_temps.get(h, self._outdoor_temps.get(
                hour_of_day, _DEFAULT_OUTDOOR_TEMPS.get(hour_of_day, 5.0)
            ))
            price = self._prices.get(h, self._prices.get(
                hour_of_day, _DEFAULT_PRICES.get(hour_of_day, 30.0)
            ))
            pv = self._pv_forecast.get(h, self._pv_forecast.get(hour_of_day, 0.0))
            cop = self.get_cop(outdoor)
            eff_cost = price / cop

            scored_hours.append({
                "h": h,
                "outdoor": outdoor,
                "price": price,
                "pv": pv,
                "cop": cop,
                "eff_cost": eff_cost,
            })

        # Rank hours by strategy preference
        if self._strategy == "cop_optimized":
            # Sort by effective cost (price/COP) — best value first
            ranked = sorted(scored_hours, key=lambda x: x["eff_cost"])
        elif self._strategy == "price_optimized":
            # Sort by raw price — cheapest first
            ranked = sorted(scored_hours, key=lambda x: x["price"])
        elif self._strategy == "solar_boost":
            # Sort by PV surplus descending, then by effective cost
            ranked = sorted(scored_hours, key=lambda x: (-x["pv"], x["eff_cost"]))
        else:
            # comfort_first — all hours equally available
            ranked = scored_hours[:]

        # Determine which hours to run
        preferred_hours: set[int] = set()

        if self._strategy == "comfort_first":
            # Run whenever temperature drops below target
            # We'll handle this in the forward simulation
            pass
        else:
            # Select top hours up to max runtime
            max_h = min(self.config.max_runtime_hours_per_day, 18)
            # Scale for multi-day horizon
            max_total = max_h * (horizon_hours / 24)
            for entry in ranked[:int(max_total)]:
                preferred_hours.add(entry["h"])

        # Forward simulation
        for h in range(horizon_hours):
            hour_of_day = h % 24
            ts = (now + timedelta(hours=h)).isoformat()

            outdoor = self._outdoor_temps.get(h, self._outdoor_temps.get(
                hour_of_day, _DEFAULT_OUTDOOR_TEMPS.get(hour_of_day, 5.0)
            ))
            price = self._prices.get(h, self._prices.get(
                hour_of_day, _DEFAULT_PRICES.get(hour_of_day, 30.0)
            ))
            pv = self._pv_forecast.get(h, self._pv_forecast.get(hour_of_day, 0.0))
            cop = self.get_cop(outdoor)

            if cop > best_cop[1]:
                best_cop = (h, cop)
            if cop < worst_cop[1]:
                worst_cop = (h, cop)

            # Determine action
            action = "off"
            power = 0.0
            heat_kwh = 0.0
            cost = 0.0
            reason = "idle"

            # Priority 1: DHW if water below minimum
            if hw_temp < self.config.hot_water_min_c:
                action = "dhw"
                power = self.config.nominal_power_kw
                heat_kwh = power * cop
                dhw_needed = self._dhw_heat_needed_kwh()
                heat_kwh = min(heat_kwh, dhw_needed)
                power = heat_kwh / cop if cop > 0 else 0
                cost = power * price
                hw_temp = min(
                    self.config.hot_water_target_c,
                    hw_temp + (heat_kwh * 1000) / (self.config.hot_water_tank_l * 1.16),
                )
                dhw_cycles += 1
                reason = f"DHW reheat ({hw_temp:.0f}°C < {self.config.hot_water_min_c:.0f}°C min)"

            # Priority 2: Defrost check (air-source only)
            elif (
                self.config.pump_type != "ground_water"
                and needs_defrost(outdoor, self.config.defrost_threshold_c)
                and h % 4 == 0  # defrost every ~4h when conditions warrant
            ):
                action = "defrost"
                power = self.config.nominal_power_kw * 0.3
                heat_kwh = 0.0  # defrost doesn't heat the home
                cost = power * price
                defrost_hours += 1
                reason = f"Defrost cycle (outdoor {outdoor:.1f}°C)"

            # Priority 3: Solar boost — free heating from PV surplus
            elif pv > 1.0:
                action = "solar_boost"
                power = min(pv, self.config.nominal_power_kw)
                heat_kwh = power * cop
                cost = 0.0  # free from PV
                room_temp = self._room_temp_after_hour(room_temp, outdoor, heat_kwh)
                reason = f"PV surplus {pv:.1f} kW"

            # Priority 4: Heating based on strategy
            elif self._strategy == "comfort_first":
                # Heat whenever room drops below target
                if room_temp < self.config.target_room_temp_c - 0.5:
                    action = "heat"
                    power = self.config.nominal_power_kw
                    heat_kwh = power * cop
                    cost = power * price
                    room_temp = self._room_temp_after_hour(room_temp, outdoor, heat_kwh)
                    reason = f"Comfort: room {room_temp:.1f}°C < target"
                else:
                    # Natural cooling
                    room_temp = self._room_temp_after_hour(room_temp, outdoor, 0)
                    reason = f"Room at target ({room_temp:.1f}°C)"

            elif h in preferred_hours:
                # Check if heating is beneficial
                temp_deficit = self.config.target_room_temp_c - room_temp
                heat_loss = self._heat_loss_kw(room_temp, outdoor)

                if temp_deficit > -2.0 and heat_loss > 0:
                    # Pre-heat or maintain — allow up to 2°C above target
                    action = "heat"
                    power = self.config.nominal_power_kw
                    heat_kwh = power * cop
                    cost = power * price
                    room_temp = self._room_temp_after_hour(room_temp, outdoor, heat_kwh)
                    reason = f"Scheduled ({self._strategy}): eff.cost {price/cop:.1f} ct/kWh_th"
                else:
                    room_temp = self._room_temp_after_hour(room_temp, outdoor, 0)
                    reason = f"Room warm enough ({room_temp:.1f}°C), skipped"
            else:
                # Off — natural cooling
                room_temp = self._room_temp_after_hour(room_temp, outdoor, 0)
                reason = "Not scheduled"

            # Hot water natural cooling (~0.3°C/h)
            if action != "dhw":
                hw_temp = max(hw_temp - 0.3, 20.0)

            if action != "off":
                runtime += 1
                total_heat += heat_kwh
                total_elec += power
                total_cost += cost

            hours_data.append(HeatPumpHour(
                hour=h,
                timestamp=ts,
                action=action,
                power_kw=round(power, 2),
                cop=round(cop, 2),
                outdoor_temp_c=round(outdoor, 1),
                electricity_price_ct=round(price, 1),
                cost_ct=round(cost, 1),
                heat_delivered_kwh=round(heat_kwh, 2),
                room_temp_c=round(room_temp, 1),
                hot_water_temp_c=round(hw_temp, 1),
                pv_surplus_kw=round(pv, 2),
                reason=reason,
            ))

        avg_cop = total_heat / total_elec if total_elec > 0 else 0.0

        schedule = HeatPumpSchedule(
            hours=[self._hour_to_dict(h) for h in hours_data],
            total_heat_kwh=round(total_heat, 2),
            total_electricity_kwh=round(total_elec, 2),
            total_cost_eur=round(total_cost / 100, 2),
            avg_cop=round(avg_cop, 2),
            best_cop_hour=best_cop[0],
            worst_cop_hour=worst_cop[0],
            dhw_cycles=dhw_cycles,
            defrost_hours=defrost_hours,
            runtime_hours=runtime,
            strategy=self._strategy,
            generated_at=now.isoformat(),
        )

        self._last_schedule = schedule
        return schedule

    def get_status(self) -> HeatPumpStatus:
        """Get current heat pump status."""
        outdoor = self._outdoor_temps.get(0, _DEFAULT_OUTDOOR_TEMPS.get(0, 5.0))
        cop = self.get_cop(outdoor)

        current_action = "off"
        next_action = ""
        next_action_at = ""

        if self._last_schedule and self._last_schedule.hours:
            for h_data in self._last_schedule.hours:
                if h_data.get("action", "off") != "off":
                    current_action = h_data["action"]
                    break

            for h_data in self._last_schedule.hours[1:]:
                if h_data.get("action", "off") != "off":
                    next_action = h_data["action"]
                    next_action_at = h_data.get("timestamp", "")
                    break

        return HeatPumpStatus(
            pump_type=self.config.pump_type,
            current_action=current_action,
            current_cop=round(cop, 2),
            current_power_kw=self.config.nominal_power_kw if current_action != "off" else 0.0,
            room_temp_c=round(self.config.current_room_temp_c, 1),
            target_room_temp_c=self.config.target_room_temp_c,
            hot_water_temp_c=round(self.config.current_hot_water_temp_c, 1),
            hot_water_target_c=self.config.hot_water_target_c,
            outdoor_temp_c=round(outdoor, 1),
            runtime_today_h=self._runtime_today,
            heat_today_kwh=round(self._heat_today, 2),
            electricity_today_kwh=round(self._electricity_today, 2),
            cost_today_eur=round(self._cost_today / 100, 2),
            avg_cop_today=round(
                self._heat_today / self._electricity_today
                if self._electricity_today > 0
                else 0.0,
                2,
            ),
            strategy=self._strategy,
            next_action=next_action,
            next_action_at=next_action_at,
        )

    @staticmethod
    def _hour_to_dict(h: HeatPumpHour) -> dict[str, Any]:
        return {
            "hour": h.hour,
            "timestamp": h.timestamp,
            "action": h.action,
            "power_kw": h.power_kw,
            "cop": h.cop,
            "outdoor_temp_c": h.outdoor_temp_c,
            "electricity_price_ct": h.electricity_price_ct,
            "cost_ct": h.cost_ct,
            "heat_delivered_kwh": h.heat_delivered_kwh,
            "room_temp_c": h.room_temp_c,
            "hot_water_temp_c": h.hot_water_temp_c,
            "pv_surplus_kw": h.pv_surplus_kw,
            "reason": h.reason,
        }
