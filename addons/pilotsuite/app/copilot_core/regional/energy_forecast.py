"""Energy Forecast Dashboard — 48h Forecast Data (v5.20.0).

Combines solar forecast, electricity prices, weather impact, and
consumption patterns into a unified 48-hour energy forecast.
Dashboard-ready JSON for Lovelace cards and frontend rendering.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class ForecastHour:
    """Single hour in the energy forecast."""

    hour: int  # 0-47 (0 = current hour)
    timestamp: str  # ISO
    # Solar
    pv_factor: float  # 0-1
    pv_kw_estimated: float  # estimated kW at peak capacity
    is_daylight: bool
    # Price
    price_ct_kwh: float
    price_level: str  # very_low/low/normal/high/very_high
    # Weather
    weather_impact: str  # none/low/moderate/high
    pv_reduction_pct: int  # 0-100
    # Recommendation
    action: str  # charge/discharge/hold/shift/consume
    score: float  # 0-10 overall favorability


@dataclass
class ForecastSummary:
    """Summary of 48h forecast."""

    total_hours: int
    avg_price_ct: float
    min_price_ct: float
    max_price_ct: float
    cheapest_hour: str
    most_expensive_hour: str
    avg_pv_factor: float
    daylight_hours: int
    best_charge_window: str
    best_consume_window: str
    total_pv_kwh_estimated: float
    weather_impacted_hours: int


@dataclass
class DashboardCard:
    """Dashboard card data for Lovelace."""

    card_type: str  # "price_chart", "pv_forecast", "recommendation", "overview"
    title_de: str
    title_en: str
    data: dict
    icon: str
    color: str  # hex


@dataclass
class EnergyForecastDashboard:
    """Complete dashboard data bundle."""

    forecast: list[dict]
    summary: dict
    cards: list[dict]
    generated_at: str


# ── Main Forecast Engine ─────────────────────────────────────────────────

class EnergyForecastEngine:
    """Generates 48h energy forecast from regional data.

    Combines:
    - Solar position data for PV forecast
    - Electricity price data (or TOU defaults)
    - Weather warning impacts
    - Scored recommendations per hour
    """

    def __init__(
        self,
        latitude: float = 51.0,
        longitude: float = 10.0,
        pv_peak_kw: float = 10.0,
        grid_price_ct: float = 30.0,
    ):
        self._lat = latitude
        self._lon = longitude
        self._pv_peak = pv_peak_kw
        self._default_price = grid_price_ct

        # External data (updated via set_* methods)
        self._hourly_prices: dict[int, float] = {}  # hour -> ct/kWh
        self._weather_impacts: dict[int, tuple[str, int]] = {}  # hour -> (level, pv_reduction)
        self._last_generated: float = 0

    def set_pv_peak(self, kw: float) -> None:
        """Set PV system peak capacity."""
        self._pv_peak = kw

    def update_location(self, lat: float, lon: float) -> None:
        """Update location for solar calculations."""
        self._lat = lat
        self._lon = lon

    def set_hourly_prices(self, prices: dict[int, float]) -> None:
        """Set hourly prices (hour 0-47 -> ct/kWh)."""
        self._hourly_prices = prices

    def set_weather_impacts(self, impacts: dict[int, tuple[str, int]]) -> None:
        """Set weather impacts (hour 0-47 -> (level, pv_reduction_pct))."""
        self._weather_impacts = impacts

    def import_tariff_data(self, hourly_prices: list[dict]) -> None:
        """Import prices from tariff engine format."""
        now = datetime.now()
        for p in hourly_prices:
            try:
                start = datetime.fromisoformat(p.get("start_timestamp", ""))
                delta = start - now
                hour_offset = int(delta.total_seconds() / 3600)
                if 0 <= hour_offset < 48:
                    self._hourly_prices[hour_offset] = p.get("price_ct_kwh", self._default_price)
            except (ValueError, TypeError):
                pass

    def import_warning_data(self, warning_impacts: list[dict]) -> None:
        """Import impacts from weather warning manager."""
        for imp in warning_impacts:
            reduction = imp.get("pv_reduction_pct", 0)
            level = imp.get("pv_impact", "none")
            # Apply to all forecast hours (simplified — a real implementation
            # would use warning start/end times)
            for h in range(48):
                existing = self._weather_impacts.get(h, ("none", 0))
                if reduction > existing[1]:
                    self._weather_impacts[h] = (level, reduction)

    def _solar_factor(self, dt: datetime) -> tuple[float, bool]:
        """Calculate PV factor for a given datetime."""
        doy = dt.timetuple().tm_yday
        lat_rad = math.radians(self._lat)

        # Declination
        decl = math.radians(-23.45 * math.cos(math.radians(360 / 365 * (doy + 10))))

        # Hour angle at sunrise
        cos_ha = -math.tan(lat_rad) * math.tan(decl)
        cos_ha = max(-1.0, min(1.0, cos_ha))
        ha_sunrise = math.acos(cos_ha)

        # Equation of time
        b = math.radians(360 / 365 * (doy - 81))
        eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)

        # DST offset
        tz_offset = 2.0 if 3 <= dt.month <= 10 else 1.0

        # Solar noon
        solar_noon_h = (720 - 4 * self._lon - eot + tz_offset * 60) / 60.0
        day_length_h = 2 * math.degrees(ha_sunrise) / 15.0
        sunrise_h = solar_noon_h - day_length_h / 2
        sunset_h = solar_noon_h + day_length_h / 2

        current_h = dt.hour + dt.minute / 60.0
        is_daylight = sunrise_h <= current_h <= sunset_h

        if not is_daylight:
            return 0.0, False

        # Elevation
        hour_angle = math.radians(15 * (current_h - solar_noon_h))
        sin_elev = (
            math.sin(lat_rad) * math.sin(decl)
            + math.cos(lat_rad) * math.cos(decl) * math.cos(hour_angle)
        )
        elevation = math.degrees(math.asin(max(-1, min(1, sin_elev))))

        factor = min(max(elevation / 60.0, 0), 1.0)
        return round(factor, 3), True

    def _default_tou_price(self, hour: int) -> float:
        """Default time-of-use price for an hour of day."""
        # German typical TOU curve
        h = hour % 24
        if 0 <= h <= 5:
            return 22.0
        elif 6 <= h <= 9:
            return 32.0
        elif 10 <= h <= 16:
            return 31.0
        elif 17 <= h <= 20:
            return 35.0
        else:
            return 25.0

    def _score_hour(
        self, pv_factor: float, price_ct: float, weather_impact: str, pv_reduction: int
    ) -> tuple[str, float]:
        """Score an hour for consumption favorability (0-10)."""
        score = 5.0  # baseline

        # PV bonus (self-consumption is always good)
        effective_pv = pv_factor * (1 - pv_reduction / 100.0)
        score += effective_pv * 3.0  # up to +3

        # Price scoring (lower = better)
        if price_ct <= 20:
            score += 2.0
        elif price_ct <= 25:
            score += 1.0
        elif price_ct >= 35:
            score -= 1.5
        elif price_ct >= 40:
            score -= 3.0

        # Weather penalty
        if weather_impact == "high":
            score -= 1.0
        elif weather_impact == "moderate":
            score -= 0.5

        score = max(0, min(10, score))

        # Determine action
        if score >= 7.5:
            action = "consume"
        elif score >= 6.0:
            action = "charge"
        elif score >= 4.0:
            action = "hold"
        elif score >= 2.5:
            action = "shift"
        else:
            action = "discharge"

        return action, round(score, 1)

    def generate_forecast(self) -> list[ForecastHour]:
        """Generate 48-hour energy forecast."""
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        forecast = []

        for h in range(48):
            dt = now + timedelta(hours=h)

            # Solar
            pv_factor, is_daylight = self._solar_factor(dt)

            # Price
            price_ct = self._hourly_prices.get(h, self._default_tou_price(dt.hour))

            # Price level classification
            avg_price = sum(
                self._hourly_prices.get(i, self._default_tou_price((now + timedelta(hours=i)).hour))
                for i in range(48)
            ) / 48

            ratio = price_ct / avg_price if avg_price > 0 else 1.0
            if ratio <= 0.6:
                price_level = "very_low"
            elif ratio <= 0.85:
                price_level = "low"
            elif ratio <= 1.15:
                price_level = "normal"
            elif ratio <= 1.4:
                price_level = "high"
            else:
                price_level = "very_high"

            # Weather
            weather_impact, pv_reduction = self._weather_impacts.get(h, ("none", 0))

            # Effective PV
            effective_pv = pv_factor * (1 - pv_reduction / 100.0)
            pv_kw = round(effective_pv * self._pv_peak, 2)

            # Score
            action, score = self._score_hour(pv_factor, price_ct, weather_impact, pv_reduction)

            hour = ForecastHour(
                hour=h,
                timestamp=dt.isoformat(),
                pv_factor=pv_factor,
                pv_kw_estimated=pv_kw,
                is_daylight=is_daylight,
                price_ct_kwh=round(price_ct, 2),
                price_level=price_level,
                weather_impact=weather_impact,
                pv_reduction_pct=pv_reduction,
                action=action,
                score=score,
            )
            forecast.append(hour)

        self._last_generated = time.time()
        return forecast

    def generate_summary(self, forecast: list[ForecastHour] | None = None) -> ForecastSummary:
        """Generate forecast summary."""
        if forecast is None:
            forecast = self.generate_forecast()

        prices = [h.price_ct_kwh for h in forecast]
        pv_factors = [h.pv_factor for h in forecast]
        daylight = [h for h in forecast if h.is_daylight]
        weather_impacted = [h for h in forecast if h.weather_impact != "none"]

        # Find best windows
        best_charge = max(forecast, key=lambda h: h.score if h.action in ("charge", "consume") else 0)
        best_consume = max(forecast, key=lambda h: h.score)

        # Cheapest/most expensive
        cheapest = min(forecast, key=lambda h: h.price_ct_kwh)
        most_expensive = max(forecast, key=lambda h: h.price_ct_kwh)

        # Estimated total PV kWh
        total_pv = sum(h.pv_kw_estimated for h in forecast)  # sum of hourly kW ≈ kWh

        return ForecastSummary(
            total_hours=len(forecast),
            avg_price_ct=round(sum(prices) / len(prices), 2),
            min_price_ct=round(min(prices), 2),
            max_price_ct=round(max(prices), 2),
            cheapest_hour=cheapest.timestamp[:16],
            most_expensive_hour=most_expensive.timestamp[:16],
            avg_pv_factor=round(sum(pv_factors) / len(pv_factors), 3),
            daylight_hours=len(daylight),
            best_charge_window=best_charge.timestamp[:16],
            best_consume_window=best_consume.timestamp[:16],
            total_pv_kwh_estimated=round(total_pv, 1),
            weather_impacted_hours=len(weather_impacted),
        )

    def generate_dashboard_cards(
        self, forecast: list[ForecastHour] | None = None
    ) -> list[DashboardCard]:
        """Generate dashboard cards for Lovelace."""
        if forecast is None:
            forecast = self.generate_forecast()

        summary = self.generate_summary(forecast)
        cards = []

        # 1. Price chart card
        price_data = [
            {"hour": h.hour, "timestamp": h.timestamp, "price_ct": h.price_ct_kwh, "level": h.price_level}
            for h in forecast
        ]
        cards.append(DashboardCard(
            card_type="price_chart",
            title_de="Strompreis 48h",
            title_en="Electricity Price 48h",
            data={
                "series": price_data,
                "avg": summary.avg_price_ct,
                "min": summary.min_price_ct,
                "max": summary.max_price_ct,
                "cheapest_hour": summary.cheapest_hour,
            },
            icon="mdi:chart-line",
            color="#2196F3",
        ))

        # 2. PV forecast card
        pv_data = [
            {"hour": h.hour, "timestamp": h.timestamp, "pv_kw": h.pv_kw_estimated,
             "pv_factor": h.pv_factor, "reduction": h.pv_reduction_pct}
            for h in forecast if h.is_daylight
        ]
        cards.append(DashboardCard(
            card_type="pv_forecast",
            title_de="PV-Prognose 48h",
            title_en="PV Forecast 48h",
            data={
                "series": pv_data,
                "total_kwh": summary.total_pv_kwh_estimated,
                "daylight_hours": summary.daylight_hours,
                "peak_kw": self._pv_peak,
            },
            icon="mdi:solar-panel",
            color="#FF9800",
        ))

        # 3. Recommendation card
        top_actions = sorted(forecast, key=lambda h: -h.score)[:6]
        rec_data = [
            {"hour": h.hour, "timestamp": h.timestamp, "action": h.action,
             "score": h.score, "price_ct": h.price_ct_kwh, "pv_kw": h.pv_kw_estimated}
            for h in top_actions
        ]
        cards.append(DashboardCard(
            card_type="recommendation",
            title_de="Empfehlungen",
            title_en="Recommendations",
            data={
                "top_hours": rec_data,
                "best_charge": summary.best_charge_window,
                "best_consume": summary.best_consume_window,
            },
            icon="mdi:lightbulb-on",
            color="#4CAF50",
        ))

        # 4. Overview card
        cards.append(DashboardCard(
            card_type="overview",
            title_de="48h Übersicht",
            title_en="48h Overview",
            data={
                "total_hours": summary.total_hours,
                "avg_price_ct": summary.avg_price_ct,
                "total_pv_kwh": summary.total_pv_kwh_estimated,
                "daylight_hours": summary.daylight_hours,
                "weather_impacted_hours": summary.weather_impacted_hours,
                "price_spread_ct": round(summary.max_price_ct - summary.min_price_ct, 2),
            },
            icon="mdi:view-dashboard",
            color="#9C27B0",
        ))

        return cards

    def generate_dashboard(self) -> EnergyForecastDashboard:
        """Generate complete dashboard data."""
        forecast = self.generate_forecast()
        summary = self.generate_summary(forecast)
        cards = self.generate_dashboard_cards(forecast)

        return EnergyForecastDashboard(
            forecast=[asdict(h) for h in forecast],
            summary=asdict(summary),
            cards=[asdict(c) for c in cards],
            generated_at=datetime.now().isoformat(),
        )
