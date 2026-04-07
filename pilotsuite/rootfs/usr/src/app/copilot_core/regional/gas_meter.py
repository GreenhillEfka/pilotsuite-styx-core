"""Gas Meter & Gastherme — Impulse Counter, Pricing, Statistics (v6.3.0).

Supports:
- Impulse-based gas meters (binary_sensor pulse counting)
- Direct m³ reading (from HA counter or utility meter)
- Configurable impulse factor (default 0.01 m³/impulse)
- Gas price tracking (regional average / manual input)
- kWh conversion via calorific value (Brennwert)
- Daily/weekly/monthly statistics
- Cost forecasting
- Initial meter reading import
"""

from __future__ import annotations

import logging
import statistics as stats_module
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Configuration ───────────────────────────────────────────────────────────

# German average gas prices (ct/kWh) by region — zero-config defaults
_REGIONAL_GAS_PRICES_CT_KWH = {
    "nord": 8.5,
    "ost": 9.0,
    "sued": 8.8,
    "west": 8.3,
    "default": 8.6,  # Bundesdurchschnitt
}

# Gas properties
_DEFAULT_CALORIFIC_VALUE_KWH_M3 = 10.3  # Brennwert (Hi) — typical H-Gas
_DEFAULT_Z_NUMBER = 0.9524  # Zustandszahl — pressure/temperature correction
_DEFAULT_IMPULSE_FACTOR_M3 = 0.01  # 1 impulse = 0.01 m³
_DEFAULT_IMPULSE_FACTOR_M3_ALT = 0.10  # some counters use 0.10 m³


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class GasMeterConfig:
    """Gas meter configuration."""

    impulse_factor_m3: float = _DEFAULT_IMPULSE_FACTOR_M3
    calorific_value_kwh_m3: float = _DEFAULT_CALORIFIC_VALUE_KWH_M3
    z_number: float = _DEFAULT_Z_NUMBER
    gas_price_ct_kwh: float | None = None  # None = use regional default
    region: str = "default"
    initial_meter_reading_m3: float = 0.0
    binary_sensor_entity: str = "binary_sensor.gasdurchflusssensor"
    counter_entity: str = "counter.gaszaehler"
    currency: str = "EUR"


@dataclass
class GasReading:
    """A single gas reading."""

    timestamp: datetime
    meter_m3: float
    impulses_delta: int = 0
    source: str = "impulse"  # impulse, manual, counter


@dataclass
class GasPeriodStats:
    """Statistics for a time period."""

    period: str  # "today", "yesterday", "week", "month", "year"
    start: datetime | None = None
    end: datetime | None = None
    consumption_m3: float = 0.0
    consumption_kwh: float = 0.0
    cost_eur: float = 0.0
    avg_daily_m3: float = 0.0
    avg_daily_kwh: float = 0.0
    avg_daily_cost: float = 0.0
    readings: int = 0


@dataclass
class GasForecast:
    """Gas consumption forecast."""

    period: str  # "month", "year"
    estimated_m3: float = 0.0
    estimated_kwh: float = 0.0
    estimated_cost_eur: float = 0.0
    confidence: float = 0.0
    based_on_days: int = 0
    trend: str = "stabil"  # steigend, fallend, stabil


@dataclass
class GasDashboard:
    """Complete gas meter dashboard."""

    current_meter_m3: float = 0.0
    total_impulses: int = 0
    today: GasPeriodStats = field(default_factory=lambda: GasPeriodStats(period="today"))
    yesterday: GasPeriodStats = field(default_factory=lambda: GasPeriodStats(period="yesterday"))
    week: GasPeriodStats = field(default_factory=lambda: GasPeriodStats(period="week"))
    month: GasPeriodStats = field(default_factory=lambda: GasPeriodStats(period="month"))
    year: GasPeriodStats = field(default_factory=lambda: GasPeriodStats(period="year"))
    forecast_month: GasForecast = field(default_factory=lambda: GasForecast(period="month"))
    forecast_year: GasForecast = field(default_factory=lambda: GasForecast(period="year"))
    gas_price_ct_kwh: float = 0.0
    gas_price_eur_m3: float = 0.0
    calorific_value: float = _DEFAULT_CALORIFIC_VALUE_KWH_M3
    config: dict[str, Any] = field(default_factory=dict)


# ── Engine ──────────────────────────────────────────────────────────────────


class GasMeterEngine:
    """Gas meter tracking engine with impulse counting, pricing, and forecasting."""

    def __init__(self, config: GasMeterConfig | None = None) -> None:
        self._config = config or GasMeterConfig()
        self._impulse_count: int = 0
        self._readings: list[GasReading] = []
        self._daily_consumption: dict[str, float] = {}  # date_str -> m³
        self._current_meter_m3: float = self._config.initial_meter_reading_m3

        # Resolve gas price
        if self._config.gas_price_ct_kwh is None:
            self._gas_price_ct_kwh = _REGIONAL_GAS_PRICES_CT_KWH.get(
                self._config.region,
                _REGIONAL_GAS_PRICES_CT_KWH["default"],
            )
        else:
            self._gas_price_ct_kwh = self._config.gas_price_ct_kwh

    # ── Configuration ───────────────────────────────────────────────────

    def update_config(self, **kwargs: Any) -> GasMeterConfig:
        """Update configuration dynamically."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

        # Re-resolve gas price
        if "gas_price_ct_kwh" in kwargs:
            self._gas_price_ct_kwh = kwargs["gas_price_ct_kwh"] or _REGIONAL_GAS_PRICES_CT_KWH.get(
                self._config.region,
                _REGIONAL_GAS_PRICES_CT_KWH["default"],
            )
        elif "region" in kwargs and self._config.gas_price_ct_kwh is None:
            self._gas_price_ct_kwh = _REGIONAL_GAS_PRICES_CT_KWH.get(
                kwargs["region"],
                _REGIONAL_GAS_PRICES_CT_KWH["default"],
            )

        return self._config

    def set_initial_reading(self, meter_m3: float) -> None:
        """Set or update initial meter reading."""
        delta = meter_m3 - self._config.initial_meter_reading_m3
        self._config.initial_meter_reading_m3 = meter_m3
        self._current_meter_m3 = meter_m3
        logger.info("Zählerstand auf %.2f m³ gesetzt", meter_m3)

    def set_gas_price(self, price_ct_kwh: float) -> None:
        """Set gas price in ct/kWh."""
        self._gas_price_ct_kwh = price_ct_kwh
        self._config.gas_price_ct_kwh = price_ct_kwh
        logger.info("Gaspreis auf %.2f ct/kWh gesetzt", price_ct_kwh)

    # ── Data ingestion ──────────────────────────────────────────────────

    def record_impulse(self, timestamp: datetime | None = None) -> float:
        """Record a single impulse from the binary sensor.

        Returns:
            New meter reading in m³.
        """
        ts = timestamp or datetime.now(tz=timezone.utc)
        self._impulse_count += 1
        delta_m3 = self._config.impulse_factor_m3
        self._current_meter_m3 += delta_m3

        reading = GasReading(
            timestamp=ts,
            meter_m3=self._current_meter_m3,
            impulses_delta=1,
            source="impulse",
        )
        self._readings.append(reading)
        self._update_daily(ts, delta_m3)

        return self._current_meter_m3

    def record_impulses(self, count: int, timestamp: datetime | None = None) -> float:
        """Record multiple impulses at once.

        Returns:
            New meter reading in m³.
        """
        ts = timestamp or datetime.now(tz=timezone.utc)
        self._impulse_count += count
        delta_m3 = count * self._config.impulse_factor_m3
        self._current_meter_m3 += delta_m3

        reading = GasReading(
            timestamp=ts,
            meter_m3=self._current_meter_m3,
            impulses_delta=count,
            source="impulse",
        )
        self._readings.append(reading)
        self._update_daily(ts, delta_m3)

        return self._current_meter_m3

    def record_meter_reading(self, meter_m3: float,
                              timestamp: datetime | None = None) -> float:
        """Record a direct meter reading (from counter entity or manual).

        Returns:
            Consumed m³ since last reading.
        """
        ts = timestamp or datetime.now(tz=timezone.utc)
        delta_m3 = max(0.0, meter_m3 - self._current_meter_m3)
        self._current_meter_m3 = meter_m3

        reading = GasReading(
            timestamp=ts,
            meter_m3=meter_m3,
            impulses_delta=0,
            source="counter",
        )
        self._readings.append(reading)
        if delta_m3 > 0:
            self._update_daily(ts, delta_m3)

        return delta_m3

    # ── Conversions ─────────────────────────────────────────────────────

    def m3_to_kwh(self, m3: float) -> float:
        """Convert m³ to kWh using calorific value and Z-number.

        Formula: kWh = m³ × Brennwert × Zustandszahl
        """
        return m3 * self._config.calorific_value_kwh_m3 * self._config.z_number

    def kwh_to_cost_eur(self, kwh: float) -> float:
        """Convert kWh to EUR."""
        return kwh * self._gas_price_ct_kwh / 100.0

    def m3_to_cost_eur(self, m3: float) -> float:
        """Convert m³ directly to EUR."""
        return self.kwh_to_cost_eur(self.m3_to_kwh(m3))

    @property
    def gas_price_eur_per_m3(self) -> float:
        """Gas price in EUR/m³."""
        return self.m3_to_cost_eur(1.0)

    # ── Statistics ──────────────────────────────────────────────────────

    def get_period_stats(self, period: str) -> GasPeriodStats:
        """Get statistics for a time period.

        Args:
            period: "today", "yesterday", "week", "month", "year"
        """
        now = datetime.now(tz=timezone.utc)
        start, end = self._period_range(period, now)

        consumption_m3 = 0.0
        reading_count = 0

        for date_str, daily_m3 in self._daily_consumption.items():
            try:
                day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if start <= day <= end:
                consumption_m3 += daily_m3
                reading_count += 1

        consumption_kwh = self.m3_to_kwh(consumption_m3)
        cost_eur = self.kwh_to_cost_eur(consumption_kwh)

        days = max(1, (end - start).days + 1)
        actual_days = max(1, reading_count) if reading_count > 0 else days

        return GasPeriodStats(
            period=period,
            start=start,
            end=end,
            consumption_m3=round(consumption_m3, 3),
            consumption_kwh=round(consumption_kwh, 2),
            cost_eur=round(cost_eur, 2),
            avg_daily_m3=round(consumption_m3 / actual_days, 3),
            avg_daily_kwh=round(consumption_kwh / actual_days, 2),
            avg_daily_cost=round(cost_eur / actual_days, 2),
            readings=reading_count,
        )

    def get_forecast(self, period: str = "month") -> GasForecast:
        """Forecast gas consumption.

        Uses recent daily averages to project future consumption.
        """
        now = datetime.now(tz=timezone.utc)

        # Collect recent daily values (last 30 days)
        recent_days: list[float] = []
        for i in range(30):
            day = now - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            if day_str in self._daily_consumption:
                recent_days.append(self._daily_consumption[day_str])

        if not recent_days:
            return GasForecast(period=period, confidence=0.0, based_on_days=0)

        avg_daily_m3 = stats_module.mean(recent_days)
        based_on = len(recent_days)

        # Trend detection
        if len(recent_days) >= 7:
            first_half = stats_module.mean(recent_days[len(recent_days) // 2:])
            second_half = stats_module.mean(recent_days[:len(recent_days) // 2])
            if second_half > first_half * 1.1:
                trend = "steigend"
            elif second_half < first_half * 0.9:
                trend = "fallend"
            else:
                trend = "stabil"
        else:
            trend = "stabil"

        # Days in forecast period
        if period == "month":
            # Days remaining in current month
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            days_remaining = (next_month - now).days
            total_days = (next_month - now.replace(day=1)).days
            # Already consumed this month
            month_so_far = self.get_period_stats("month")
            consumed_m3 = month_so_far.consumption_m3
            estimated_m3 = consumed_m3 + avg_daily_m3 * days_remaining
        elif period == "year":
            year_start = now.replace(month=1, day=1)
            year_end = now.replace(month=12, day=31)
            total_days = (year_end - year_start).days + 1
            days_remaining = (year_end - now).days
            year_so_far = self.get_period_stats("year")
            consumed_m3 = year_so_far.consumption_m3
            estimated_m3 = consumed_m3 + avg_daily_m3 * days_remaining
        else:
            return GasForecast(period=period, confidence=0.0, based_on_days=0)

        estimated_kwh = self.m3_to_kwh(estimated_m3)
        estimated_cost = self.kwh_to_cost_eur(estimated_kwh)

        confidence = min(1.0, based_on / 14)  # 14+ days for full confidence

        return GasForecast(
            period=period,
            estimated_m3=round(estimated_m3, 2),
            estimated_kwh=round(estimated_kwh, 1),
            estimated_cost_eur=round(estimated_cost, 2),
            confidence=round(confidence, 2),
            based_on_days=based_on,
            trend=trend,
        )

    # ── Dashboard ───────────────────────────────────────────────────────

    def get_dashboard(self) -> GasDashboard:
        """Get complete gas meter dashboard."""
        return GasDashboard(
            current_meter_m3=round(self._current_meter_m3, 3),
            total_impulses=self._impulse_count,
            today=self.get_period_stats("today"),
            yesterday=self.get_period_stats("yesterday"),
            week=self.get_period_stats("week"),
            month=self.get_period_stats("month"),
            year=self.get_period_stats("year"),
            forecast_month=self.get_forecast("month"),
            forecast_year=self.get_forecast("year"),
            gas_price_ct_kwh=round(self._gas_price_ct_kwh, 2),
            gas_price_eur_m3=round(self.gas_price_eur_per_m3, 4),
            calorific_value=self._config.calorific_value_kwh_m3,
            config={
                "impulse_factor_m3": self._config.impulse_factor_m3,
                "z_number": self._config.z_number,
                "region": self._config.region,
                "binary_sensor_entity": self._config.binary_sensor_entity,
                "counter_entity": self._config.counter_entity,
                "initial_reading_m3": self._config.initial_meter_reading_m3,
            },
        )

    # ── Helpers ─────────────────────────────────────────────────────────

    def _update_daily(self, ts: datetime, delta_m3: float) -> None:
        """Update daily consumption tracker."""
        day_str = ts.strftime("%Y-%m-%d")
        self._daily_consumption[day_str] = self._daily_consumption.get(day_str, 0.0) + delta_m3

    @staticmethod
    def _period_range(period: str, now: datetime) -> tuple[datetime, datetime]:
        """Get start/end datetime for a named period."""
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if period == "today":
            return today_start, now
        elif period == "yesterday":
            yesterday = today_start - timedelta(days=1)
            return yesterday, today_start - timedelta(seconds=1)
        elif period == "week":
            week_start = today_start - timedelta(days=now.weekday())
            return week_start, now
        elif period == "month":
            month_start = today_start.replace(day=1)
            return month_start, now
        elif period == "year":
            year_start = today_start.replace(month=1, day=1)
            return year_start, now
        else:
            return today_start, now
