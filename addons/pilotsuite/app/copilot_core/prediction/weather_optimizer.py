"""Weather-Aware Energy Optimizer (v5.11.0).

Combines weather forecasts, energy pricing, and PV prediction into
unified 48-hour optimized consumption plans.  Produces hour-by-hour
recommendations for device scheduling, battery management, and
grid interaction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta
from typing import Optional


# ── Data classes ────────────────────────────────────────────────────────────

@dataclass
class HourForecast:
    """Single-hour weather + energy forecast."""

    hour: int  # 0-47
    timestamp: str  # ISO 8601
    temperature_c: float
    cloud_cover_pct: float  # 0-100
    precipitation_mm: float
    wind_speed_kmh: float
    condition: str  # sunny / partly_cloudy / cloudy / rainy / stormy
    pv_production_kwh: float
    price_eur_kwh: float
    composite_score: float  # 0-1, higher = better for consumption


@dataclass
class BatteryAction:
    """Recommended battery action for an hour."""

    hour: int
    action: str  # "charge_from_pv", "charge_from_grid", "discharge", "hold"
    power_watts: float
    reason: str


@dataclass
class OptimizationWindow:
    """A contiguous block of hours suitable for high-consumption devices."""

    start_hour: int
    end_hour: int
    start_timestamp: str
    end_timestamp: str
    duration_hours: int
    avg_score: float
    avg_price_eur_kwh: float
    avg_pv_kwh: float
    reason: str  # "solar_surplus", "low_price", "combined"


@dataclass
class WeatherOptimizationPlan:
    """Complete 48-hour optimization plan."""

    generated_at: str
    base_date: str
    horizon_hours: int
    hourly_forecast: list[dict]
    top_windows: list[dict]
    battery_plan: list[dict]
    summary: dict
    alerts: list[str]


# ── Constants ───────────────────────────────────────────────────────────────

# Scoring weights
W_PV = 0.35
W_PRICE = 0.35
W_WEATHER = 0.15
W_DEMAND = 0.15

# Battery
BATTERY_CAPACITY_KWH = 10.0
BATTERY_MAX_CHARGE_W = 5000
BATTERY_MAX_DISCHARGE_W = 5000
BATTERY_MIN_SOC = 0.10  # 10%
BATTERY_MAX_SOC = 0.95  # 95%

# PV system defaults (Central Europe, ~8 kWp)
PV_PEAK_KWP = 8.0

# Price thresholds (EUR/kWh)
PRICE_LOW = 0.15
PRICE_HIGH = 0.35

# Cloud cover → PV efficiency factor
_CLOUD_TO_PV = [
    (0, 1.00),
    (10, 0.95),
    (25, 0.85),
    (40, 0.70),
    (60, 0.50),
    (75, 0.30),
    (90, 0.15),
    (100, 0.08),
]

# Hour → solar elevation factor (Central Europe ~48°N, averaged across year)
_SOLAR_CURVE = {
    0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0,
    5: 0.05, 6: 0.15, 7: 0.30, 8: 0.50, 9: 0.70,
    10: 0.85, 11: 0.95, 12: 1.00, 13: 0.95, 14: 0.85,
    15: 0.70, 16: 0.50, 17: 0.30, 18: 0.15, 19: 0.05,
    20: 0.0, 21: 0.0, 22: 0.0, 23: 0.0,
}

# Typical household base load by hour (watts)
_BASE_LOAD = {
    0: 300, 1: 250, 2: 250, 3: 250, 4: 250, 5: 300,
    6: 500, 7: 800, 8: 600, 9: 400, 10: 350, 11: 400,
    12: 600, 13: 500, 14: 400, 15: 350, 16: 400, 17: 600,
    18: 900, 19: 1000, 20: 800, 21: 600, 22: 500, 23: 400,
}

# Condition → weather quality factor
_CONDITION_FACTOR = {
    "sunny": 1.0,
    "partly_cloudy": 0.7,
    "cloudy": 0.4,
    "foggy": 0.3,
    "rainy": 0.2,
    "snowy": 0.15,
    "stormy": 0.1,
    "unknown": 0.5,
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _cloud_to_efficiency(cloud_pct: float) -> float:
    """Interpolate cloud cover percentage to PV efficiency factor."""
    if cloud_pct <= 0:
        return 1.0
    if cloud_pct >= 100:
        return 0.08
    for i in range(len(_CLOUD_TO_PV) - 1):
        c0, e0 = _CLOUD_TO_PV[i]
        c1, e1 = _CLOUD_TO_PV[i + 1]
        if c0 <= cloud_pct <= c1:
            t = (cloud_pct - c0) / (c1 - c0)
            return e0 + t * (e1 - e0)
    return 0.08


def _estimate_pv(hour_of_day: int, cloud_pct: float, peak_kwp: float) -> float:
    """Estimate PV production for a single hour."""
    solar = _SOLAR_CURVE.get(hour_of_day % 24, 0.0)
    cloud_eff = _cloud_to_efficiency(cloud_pct)
    return round(peak_kwp * solar * cloud_eff, 3)


def _condition_from_cloud_rain(cloud_pct: float, precip_mm: float, wind_kmh: float) -> str:
    """Derive weather condition string from raw values."""
    if wind_kmh > 60 and precip_mm > 2:
        return "stormy"
    if precip_mm > 1.0:
        return "rainy"
    if cloud_pct <= 15:
        return "sunny"
    if cloud_pct <= 50:
        return "partly_cloudy"
    if cloud_pct <= 85:
        return "cloudy"
    return "cloudy"


# ── Main Optimizer ──────────────────────────────────────────────────────────

class WeatherAwareOptimizer:
    """Combines weather, pricing, PV forecast for 48-hour optimization."""

    def __init__(
        self,
        pv_peak_kwp: float = PV_PEAK_KWP,
        battery_capacity_kwh: float = BATTERY_CAPACITY_KWH,
        battery_soc: float = 0.50,
    ):
        self._pv_peak = pv_peak_kwp
        self._battery_cap = battery_capacity_kwh
        self._battery_soc = battery_soc

    # ── Public API ──────────────────────────────────────────────────────

    def optimize(
        self,
        weather_hours: list[dict] | None = None,
        price_hours: list[float] | None = None,
        base_date: date | None = None,
        horizon: int = 48,
    ) -> WeatherOptimizationPlan:
        """Generate a full optimization plan.

        Parameters
        ----------
        weather_hours : list of dicts with keys cloud_cover_pct, precipitation_mm,
                        wind_speed_kmh, temperature_c  (one per hour, up to *horizon*)
        price_hours : list of floats (EUR/kWh), one per hour
        base_date : start date (default today)
        horizon : number of hours to plan (default 48)
        """
        base = base_date or date.today()
        now = datetime.now()

        # Build per-hour data
        hourly: list[HourForecast] = []
        for h in range(horizon):
            ts = datetime(base.year, base.month, base.day) + timedelta(hours=h)
            hod = ts.hour  # hour of day (0-23)

            # Weather
            wx = (weather_hours[h] if weather_hours and h < len(weather_hours)
                  else {})
            cloud = wx.get("cloud_cover_pct", 50.0)
            precip = wx.get("precipitation_mm", 0.0)
            wind = wx.get("wind_speed_kmh", 10.0)
            temp = wx.get("temperature_c", 15.0)
            cond = wx.get("condition") or _condition_from_cloud_rain(cloud, precip, wind)

            # PV estimate
            pv = _estimate_pv(hod, cloud, self._pv_peak)

            # Price
            price = (price_hours[h] if price_hours and h < len(price_hours)
                     else self._default_price(hod))

            # Composite score (higher = better time to consume)
            score = self._composite_score(pv, price, cond, hod)

            hourly.append(HourForecast(
                hour=h,
                timestamp=ts.isoformat(),
                temperature_c=round(temp, 1),
                cloud_cover_pct=round(cloud, 1),
                precipitation_mm=round(precip, 1),
                wind_speed_kmh=round(wind, 1),
                condition=cond,
                pv_production_kwh=pv,
                price_eur_kwh=round(price, 4),
                composite_score=round(score, 3),
            ))

        # Find optimal windows
        windows = self._find_windows(hourly)

        # Battery plan
        battery = self._battery_plan(hourly)

        # Alerts
        alerts = self._generate_alerts(hourly)

        # Summary stats
        summary = self._build_summary(hourly, windows)

        return WeatherOptimizationPlan(
            generated_at=now.isoformat(),
            base_date=base.isoformat(),
            horizon_hours=horizon,
            hourly_forecast=[asdict(h) for h in hourly],
            top_windows=[asdict(w) for w in windows[:5]],
            battery_plan=[asdict(b) for b in battery],
            summary=summary,
            alerts=alerts,
        )

    def get_best_window(
        self,
        duration_hours: int = 3,
        weather_hours: list[dict] | None = None,
        price_hours: list[float] | None = None,
        base_date: date | None = None,
    ) -> dict:
        """Find single best contiguous window of *duration_hours*."""
        plan = self.optimize(weather_hours, price_hours, base_date)
        hourly = plan.hourly_forecast

        if len(hourly) < duration_hours:
            return {"error": "Not enough forecast data"}

        best_start = 0
        best_score = -1.0
        for i in range(len(hourly) - duration_hours + 1):
            block = hourly[i:i + duration_hours]
            avg = sum(h["composite_score"] for h in block) / duration_hours
            if avg > best_score:
                best_score = avg
                best_start = i

        block = hourly[best_start:best_start + duration_hours]
        return {
            "start_hour": best_start,
            "end_hour": best_start + duration_hours,
            "start_timestamp": block[0]["timestamp"],
            "end_timestamp": block[-1]["timestamp"],
            "duration_hours": duration_hours,
            "avg_score": round(best_score, 3),
            "avg_price_eur_kwh": round(
                sum(h["price_eur_kwh"] for h in block) / duration_hours, 4
            ),
            "avg_pv_kwh": round(
                sum(h["pv_production_kwh"] for h in block) / duration_hours, 3
            ),
        }

    # ── Scoring ─────────────────────────────────────────────────────────

    def _composite_score(
        self, pv_kwh: float, price: float, condition: str, hour_of_day: int,
    ) -> float:
        """Higher score = better time to run devices."""
        # PV factor: more production → better
        pv_factor = min(pv_kwh / self._pv_peak, 1.0) if self._pv_peak > 0 else 0.0

        # Price factor: lower price → better (invert)
        price_norm = max(0, min((price - PRICE_LOW) / (PRICE_HIGH - PRICE_LOW), 1.0))
        price_factor = 1.0 - price_norm

        # Weather factor
        weather_factor = _CONDITION_FACTOR.get(condition, 0.5)

        # Demand factor: prefer off-peak hours
        base = _BASE_LOAD.get(hour_of_day, 500)
        demand_factor = 1.0 - min(base / 1000.0, 1.0)

        return (
            W_PV * pv_factor
            + W_PRICE * price_factor
            + W_WEATHER * weather_factor
            + W_DEMAND * demand_factor
        )

    @staticmethod
    def _default_price(hour: int) -> float:
        """Fallback price curve when no market data available."""
        if 0 <= hour < 6:
            return 0.18
        if 6 <= hour < 8:
            return 0.28
        if 8 <= hour < 11:
            return 0.25
        if 11 <= hour < 14:
            return 0.22
        if 14 <= hour < 17:
            return 0.24
        if 17 <= hour < 21:
            return 0.32
        return 0.20

    # ── Window detection ────────────────────────────────────────────────

    def _find_windows(self, hourly: list[HourForecast]) -> list[OptimizationWindow]:
        """Identify contiguous blocks scoring above threshold."""
        threshold = 0.50
        windows: list[OptimizationWindow] = []
        in_window = False
        start = 0

        for i, h in enumerate(hourly):
            if h.composite_score >= threshold and not in_window:
                in_window = True
                start = i
            elif h.composite_score < threshold and in_window:
                in_window = False
                self._add_window(windows, hourly, start, i)

        if in_window:
            self._add_window(windows, hourly, start, len(hourly))

        windows.sort(key=lambda w: w.avg_score, reverse=True)
        return windows

    @staticmethod
    def _add_window(
        windows: list, hourly: list[HourForecast], start: int, end: int,
    ) -> None:
        block = hourly[start:end]
        if not block:
            return
        avg_score = sum(h.composite_score for h in block) / len(block)
        avg_price = sum(h.price_eur_kwh for h in block) / len(block)
        avg_pv = sum(h.pv_production_kwh for h in block) / len(block)

        # Determine reason
        if avg_pv > 2.0 and avg_price < 0.25:
            reason = "combined"
        elif avg_pv > 2.0:
            reason = "solar_surplus"
        else:
            reason = "low_price"

        windows.append(OptimizationWindow(
            start_hour=start,
            end_hour=end,
            start_timestamp=block[0].timestamp,
            end_timestamp=block[-1].timestamp,
            duration_hours=end - start,
            avg_score=round(avg_score, 3),
            avg_price_eur_kwh=round(avg_price, 4),
            avg_pv_kwh=round(avg_pv, 3),
            reason=reason,
        ))

    # ── Battery strategy ────────────────────────────────────────────────

    def _battery_plan(self, hourly: list[HourForecast]) -> list[BatteryAction]:
        """Simple rule-based battery management."""
        actions: list[BatteryAction] = []
        soc = self._battery_soc

        for h in hourly:
            hod = int(h.timestamp[11:13]) if len(h.timestamp) > 13 else h.hour % 24
            base_load_kw = _BASE_LOAD.get(hod, 500) / 1000.0
            surplus = h.pv_production_kwh - base_load_kw

            if surplus > 0.5 and soc < BATTERY_MAX_SOC:
                # Charge from PV surplus
                charge = min(surplus, BATTERY_MAX_CHARGE_W / 1000.0,
                             (BATTERY_MAX_SOC - soc) * self._battery_cap)
                soc += charge / self._battery_cap
                actions.append(BatteryAction(
                    hour=h.hour,
                    action="charge_from_pv",
                    power_watts=round(charge * 1000),
                    reason="PV-Ueberschuss laden",
                ))
            elif h.price_eur_kwh < PRICE_LOW and soc < 0.50:
                # Cheap grid → charge
                charge = min(BATTERY_MAX_CHARGE_W / 1000.0,
                             (0.80 - soc) * self._battery_cap)
                if charge > 0:
                    soc += charge / self._battery_cap
                    actions.append(BatteryAction(
                        hour=h.hour,
                        action="charge_from_grid",
                        power_watts=round(charge * 1000),
                        reason="Guenstiger Netzstrom",
                    ))
                else:
                    actions.append(BatteryAction(
                        hour=h.hour, action="hold", power_watts=0,
                        reason="SOC ausreichend",
                    ))
            elif h.price_eur_kwh > PRICE_HIGH and soc > BATTERY_MIN_SOC + 0.1:
                # Expensive → discharge
                discharge = min(BATTERY_MAX_DISCHARGE_W / 1000.0,
                                base_load_kw,
                                (soc - BATTERY_MIN_SOC) * self._battery_cap)
                soc -= discharge / self._battery_cap
                actions.append(BatteryAction(
                    hour=h.hour,
                    action="discharge",
                    power_watts=round(discharge * 1000),
                    reason="Hoher Strompreis — Batterie nutzen",
                ))
            else:
                actions.append(BatteryAction(
                    hour=h.hour, action="hold", power_watts=0,
                    reason="Halten",
                ))

        return actions

    # ── Alerts ──────────────────────────────────────────────────────────

    @staticmethod
    def _generate_alerts(hourly: list[HourForecast]) -> list[str]:
        alerts: list[str] = []

        # Storm warning
        for h in hourly:
            if h.condition == "stormy":
                alerts.append(
                    f"Sturmwarnung um {h.timestamp[11:16]} — "
                    "PV-Anlage pruefen, Geraete sichern"
                )
                break

        # Extended cloud cover (>12h consecutive)
        run = 0
        for h in hourly:
            if h.cloud_cover_pct > 80:
                run += 1
            else:
                run = 0
            if run == 12:
                alerts.append(
                    "Langanhaltende Bewoelkung (>12h) — "
                    "erhoehter Netzbezug erwartet"
                )
                break

        # Price spike
        for h in hourly:
            if h.price_eur_kwh > 0.50:
                alerts.append(
                    f"Preisspitze um {h.timestamp[11:16]}: "
                    f"{h.price_eur_kwh:.2f} EUR/kWh — "
                    "Verbrauch verschieben empfohlen"
                )
                break

        # Frost warning (heat pump impact)
        for h in hourly:
            if h.temperature_c < -5:
                alerts.append(
                    f"Frostwarnung ({h.temperature_c:.0f}°C) — "
                    "Waermepumpe: erhoehter Verbrauch erwartet"
                )
                break

        return alerts

    # ── Summary ─────────────────────────────────────────────────────────

    @staticmethod
    def _build_summary(
        hourly: list[HourForecast],
        windows: list[OptimizationWindow],
    ) -> dict:
        if not hourly:
            return {
                "total_pv_kwh": 0, "avg_price_eur_kwh": 0,
                "best_hours": [], "worst_hours": [],
                "pv_self_consumption_potential_pct": 0,
                "optimal_windows_count": 0,
            }

        total_pv = sum(h.pv_production_kwh for h in hourly)
        avg_price = sum(h.price_eur_kwh for h in hourly) / len(hourly)

        sorted_by_score = sorted(hourly, key=lambda h: h.composite_score, reverse=True)
        best = [h.hour for h in sorted_by_score[:5]]
        worst = [h.hour for h in sorted_by_score[-5:]]

        # Self-consumption potential: hours with PV > base load
        sc_hours = sum(
            1 for h in hourly
            if h.pv_production_kwh > _BASE_LOAD.get(h.hour % 24, 500) / 1000.0
        )
        sc_pct = round(sc_hours / max(len(hourly), 1) * 100, 1)

        return {
            "total_pv_kwh": round(total_pv, 2),
            "avg_price_eur_kwh": round(avg_price, 4),
            "best_hours": best,
            "worst_hours": worst,
            "pv_self_consumption_potential_pct": sc_pct,
            "optimal_windows_count": len(windows),
        }
