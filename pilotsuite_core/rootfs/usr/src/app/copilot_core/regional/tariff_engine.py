"""Regional Tariff Engine — Dynamic Electricity Pricing (v5.18.0).

Provides location-aware electricity pricing with support for:
- aWATTar (DE/AT): Hourly day-ahead spot prices
- EPEX Spot (CH): Swiss electricity market
- Static regional defaults as fallback

Zero-config: Uses RegionalContextProvider to auto-detect the
correct pricing API based on user's country.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────

class TariffType(str, Enum):
    """Electricity tariff type."""

    FIXED = "fixed"
    DYNAMIC = "dynamic"
    TIME_OF_USE = "time_of_use"


class PriceLevel(str, Enum):
    """Relative price level classification."""

    VERY_LOW = "very_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    VERY_HIGH = "very_high"


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class HourlyPrice:
    """Price for a single hour."""

    start_timestamp: str  # ISO
    end_timestamp: str  # ISO
    price_eur_kwh: float
    price_ct_kwh: float  # ct/kWh (common in DE)
    level: str  # PriceLevel value
    is_current: bool


@dataclass
class PriceSummary:
    """Price summary for a period."""

    current_price_eur_kwh: float
    current_price_ct_kwh: float
    current_level: str
    avg_price_eur_kwh: float
    min_price_eur_kwh: float
    max_price_eur_kwh: float
    min_hour: str  # HH:MM of cheapest hour
    max_hour: str  # HH:MM of most expensive hour
    spread_eur_kwh: float  # max - min
    hours_available: int
    tariff_type: str
    source: str
    updated_at: str


@dataclass
class OptimalWindow:
    """Optimal time window for consumption."""

    start: str  # ISO
    end: str  # ISO
    duration_hours: int
    avg_price_eur_kwh: float
    avg_price_ct_kwh: float
    savings_vs_now_eur_kwh: float
    savings_pct: float


@dataclass
class TariffRecommendation:
    """Tariff-based energy recommendation."""

    action: str  # "charge_now", "wait", "discharge", "shift"
    reason_de: str
    reason_en: str
    current_price_ct: float
    optimal_price_ct: float
    savings_pct: float
    optimal_start: str
    optimal_end: str


# ── Default time-of-use tariffs ──────────────────────────────────────────

# German HT/NT (Hochtarif/Niedertarif) typical schedule
_TOU_SCHEDULE_DE = {
    # hour -> price_eur_kwh
    0: 0.22, 1: 0.22, 2: 0.22, 3: 0.22, 4: 0.22, 5: 0.22,
    6: 0.30, 7: 0.32, 8: 0.34, 9: 0.34, 10: 0.33, 11: 0.32,
    12: 0.31, 13: 0.30, 14: 0.30, 15: 0.31, 16: 0.33, 17: 0.35,
    18: 0.36, 19: 0.35, 20: 0.33, 21: 0.30, 22: 0.25, 23: 0.22,
}

# Weekend has lower prices
_TOU_WEEKEND_DE = {h: max(p - 0.05, 0.20) for h, p in _TOU_SCHEDULE_DE.items()}


# ── Price level thresholds ───────────────────────────────────────────────

def _classify_price(price: float, avg: float) -> str:
    """Classify price level relative to average."""
    if avg <= 0:
        return PriceLevel.NORMAL

    ratio = price / avg
    if ratio <= 0.6:
        return PriceLevel.VERY_LOW
    elif ratio <= 0.85:
        return PriceLevel.LOW
    elif ratio <= 1.15:
        return PriceLevel.NORMAL
    elif ratio <= 1.4:
        return PriceLevel.HIGH
    else:
        return PriceLevel.VERY_HIGH


# ── Main Tariff Engine ───────────────────────────────────────────────────

class RegionalTariffEngine:
    """Location-aware electricity pricing engine.

    Supports:
    - Dynamic pricing via aWATTar/EPEX spot market data
    - Time-of-use (HT/NT) schedules
    - Fixed rate fallback
    - Optimal consumption window calculation
    """

    def __init__(
        self,
        country: str = "DE",
        tariff_type: str = TariffType.TIME_OF_USE,
        fixed_rate_eur_kwh: float = 0.30,
        feed_in_eur_kwh: float = 0.082,
    ):
        self._country = country
        self._tariff_type = tariff_type
        self._fixed_rate = fixed_rate_eur_kwh
        self._feed_in = feed_in_eur_kwh

        # Dynamic price storage (hourly)
        self._hourly_prices: list[HourlyPrice] = []
        self._last_updated: float = 0
        self._cache_ttl: float = 900  # 15 minutes
        self._source: str = self._default_source()

    def _default_source(self) -> str:
        """Get default price source for country."""
        sources = {
            "DE": "awattar_de",
            "AT": "awattar_at",
            "CH": "epex_ch",
        }
        return sources.get(self._country, "awattar_de")

    @property
    def api_url(self) -> str:
        """Get market data API URL."""
        urls = {
            "awattar_de": "https://api.awattar.de/v1/marketdata",
            "awattar_at": "https://api.awattar.at/v1/marketdata",
            "epex_ch": "https://api.awattar.de/v1/marketdata",  # fallback
        }
        return urls.get(self._source, urls["awattar_de"])

    def update_config(
        self,
        country: str | None = None,
        tariff_type: str | None = None,
        fixed_rate: float | None = None,
        feed_in: float | None = None,
    ) -> None:
        """Update tariff configuration."""
        if country is not None:
            self._country = country
            self._source = self._default_source()
        if tariff_type is not None:
            self._tariff_type = tariff_type
        if fixed_rate is not None:
            self._fixed_rate = fixed_rate
        if feed_in is not None:
            self._feed_in = feed_in

    def process_awattar_response(self, data: dict) -> list[HourlyPrice]:
        """Parse aWATTar API response into hourly prices.

        aWATTar format: {"data": [{"start_timestamp": ms, "end_timestamp": ms,
                                    "marketprice": EUR/MWh, "unit": "Eur/MWh"}]}
        """
        prices: list[HourlyPrice] = []
        now = datetime.now()
        raw_items = data.get("data", [])

        # Collect raw prices for average calculation
        raw_values = []
        for item in raw_items:
            mwh_price = item.get("marketprice", 0)
            kwh_price = mwh_price / 1000.0  # MWh -> kWh
            # Add taxes, fees, grid charges (~0.18 EUR/kWh in DE)
            total_price = kwh_price + self._grid_surcharge()
            raw_values.append(total_price)

        avg = sum(raw_values) / len(raw_values) if raw_values else self._fixed_rate

        for i, item in enumerate(raw_items):
            try:
                start_ms = item.get("start_timestamp", 0)
                end_ms = item.get("end_timestamp", 0)
                start_dt = datetime.fromtimestamp(start_ms / 1000)
                end_dt = datetime.fromtimestamp(end_ms / 1000)

                mwh_price = item.get("marketprice", 0)
                kwh_price = mwh_price / 1000.0
                total_price = kwh_price + self._grid_surcharge()
                total_price = round(total_price, 4)

                is_current = start_dt <= now < end_dt

                price = HourlyPrice(
                    start_timestamp=start_dt.isoformat(),
                    end_timestamp=end_dt.isoformat(),
                    price_eur_kwh=total_price,
                    price_ct_kwh=round(total_price * 100, 2),
                    level=_classify_price(total_price, avg),
                    is_current=is_current,
                )
                prices.append(price)
            except Exception as exc:
                logger.debug("Failed to parse aWATTar entry: %s", exc)

        self._hourly_prices = prices
        self._last_updated = time.time()
        self._tariff_type = TariffType.DYNAMIC
        return prices

    def process_manual_prices(self, hourly_prices: list[dict]) -> list[HourlyPrice]:
        """Process manually provided hourly prices.

        Each dict: {"hour": 0-23, "price_eur_kwh": 0.xx}
        """
        prices: list[HourlyPrice] = []
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        raw_values = [p.get("price_eur_kwh", self._fixed_rate) for p in hourly_prices]
        avg = sum(raw_values) / len(raw_values) if raw_values else self._fixed_rate

        for item in hourly_prices:
            hour = int(item.get("hour", 0))
            price_val = float(item.get("price_eur_kwh", self._fixed_rate))

            start_dt = today + timedelta(hours=hour)
            end_dt = start_dt + timedelta(hours=1)
            is_current = start_dt <= now < end_dt

            price = HourlyPrice(
                start_timestamp=start_dt.isoformat(),
                end_timestamp=end_dt.isoformat(),
                price_eur_kwh=round(price_val, 4),
                price_ct_kwh=round(price_val * 100, 2),
                level=_classify_price(price_val, avg),
                is_current=is_current,
            )
            prices.append(price)

        self._hourly_prices = prices
        self._last_updated = time.time()
        return prices

    def _grid_surcharge(self) -> float:
        """Grid surcharge by country (taxes, fees, grid charges)."""
        surcharges = {
            "DE": 0.18,  # ~18 ct/kWh surcharges in Germany
            "AT": 0.14,
            "CH": 0.12,
        }
        return surcharges.get(self._country, 0.18)

    def _get_tou_prices(self) -> list[HourlyPrice]:
        """Generate time-of-use prices for today."""
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        is_weekend = now.weekday() >= 5

        schedule = _TOU_WEEKEND_DE if is_weekend else _TOU_SCHEDULE_DE
        prices: list[HourlyPrice] = []

        values = list(schedule.values())
        avg = sum(values) / len(values)

        for hour, price_val in schedule.items():
            start_dt = today + timedelta(hours=hour)
            end_dt = start_dt + timedelta(hours=1)
            is_current = start_dt <= now < end_dt

            price = HourlyPrice(
                start_timestamp=start_dt.isoformat(),
                end_timestamp=end_dt.isoformat(),
                price_eur_kwh=round(price_val, 4),
                price_ct_kwh=round(price_val * 100, 2),
                level=_classify_price(price_val, avg),
                is_current=is_current,
            )
            prices.append(price)

        return prices

    def get_hourly_prices(self) -> list[HourlyPrice]:
        """Get hourly prices (dynamic, TOU, or fixed)."""
        if self._tariff_type == TariffType.DYNAMIC and self._hourly_prices:
            return self._hourly_prices

        if self._tariff_type == TariffType.TIME_OF_USE:
            return self._get_tou_prices()

        # Fixed rate: generate 24 equal-price hours
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            HourlyPrice(
                start_timestamp=(today + timedelta(hours=h)).isoformat(),
                end_timestamp=(today + timedelta(hours=h + 1)).isoformat(),
                price_eur_kwh=self._fixed_rate,
                price_ct_kwh=round(self._fixed_rate * 100, 2),
                level=PriceLevel.NORMAL,
                is_current=(today + timedelta(hours=h)) <= now < (today + timedelta(hours=h + 1)),
            )
            for h in range(24)
        ]

    def get_current_price(self) -> HourlyPrice | None:
        """Get current hour's price."""
        for p in self.get_hourly_prices():
            if p.is_current:
                return p
        return None

    def get_summary(self) -> PriceSummary:
        """Get price summary for available hours."""
        prices = self.get_hourly_prices()

        if not prices:
            return PriceSummary(
                current_price_eur_kwh=self._fixed_rate,
                current_price_ct_kwh=round(self._fixed_rate * 100, 2),
                current_level=PriceLevel.NORMAL,
                avg_price_eur_kwh=self._fixed_rate,
                min_price_eur_kwh=self._fixed_rate,
                max_price_eur_kwh=self._fixed_rate,
                min_hour="00:00",
                max_hour="00:00",
                spread_eur_kwh=0.0,
                hours_available=0,
                tariff_type=self._tariff_type,
                source=self._source,
                updated_at="",
            )

        values = [p.price_eur_kwh for p in prices]
        avg = sum(values) / len(values)
        min_p = min(prices, key=lambda p: p.price_eur_kwh)
        max_p = max(prices, key=lambda p: p.price_eur_kwh)

        current = self.get_current_price()
        current_price = current.price_eur_kwh if current else self._fixed_rate
        current_level = current.level if current else PriceLevel.NORMAL

        # Extract hour from ISO timestamp
        def _extract_hour(iso: str) -> str:
            try:
                dt = datetime.fromisoformat(iso)
                return f"{dt.hour:02d}:00"
            except (ValueError, TypeError):
                return "00:00"

        return PriceSummary(
            current_price_eur_kwh=round(current_price, 4),
            current_price_ct_kwh=round(current_price * 100, 2),
            current_level=current_level,
            avg_price_eur_kwh=round(avg, 4),
            min_price_eur_kwh=round(min_p.price_eur_kwh, 4),
            max_price_eur_kwh=round(max_p.price_eur_kwh, 4),
            min_hour=_extract_hour(min_p.start_timestamp),
            max_hour=_extract_hour(max_p.start_timestamp),
            spread_eur_kwh=round(max_p.price_eur_kwh - min_p.price_eur_kwh, 4),
            hours_available=len(prices),
            tariff_type=self._tariff_type,
            source=self._source,
            updated_at=datetime.fromtimestamp(self._last_updated).isoformat()
            if self._last_updated
            else "",
        )

    def find_optimal_window(self, duration_hours: int = 3) -> OptimalWindow | None:
        """Find cheapest consecutive window of given duration."""
        prices = self.get_hourly_prices()
        if len(prices) < duration_hours:
            return None

        # Sort by start time
        sorted_prices = sorted(prices, key=lambda p: p.start_timestamp)

        best_avg = float("inf")
        best_start = 0

        for i in range(len(sorted_prices) - duration_hours + 1):
            window = sorted_prices[i : i + duration_hours]
            avg = sum(p.price_eur_kwh for p in window) / duration_hours
            if avg < best_avg:
                best_avg = avg
                best_start = i

        window = sorted_prices[best_start : best_start + duration_hours]
        current = self.get_current_price()
        current_price = current.price_eur_kwh if current else self._fixed_rate

        savings = current_price - best_avg
        savings_pct = (savings / current_price * 100) if current_price > 0 else 0

        return OptimalWindow(
            start=window[0].start_timestamp,
            end=window[-1].end_timestamp,
            duration_hours=duration_hours,
            avg_price_eur_kwh=round(best_avg, 4),
            avg_price_ct_kwh=round(best_avg * 100, 2),
            savings_vs_now_eur_kwh=round(max(savings, 0), 4),
            savings_pct=round(max(savings_pct, 0), 1),
        )

    def get_recommendation(self) -> TariffRecommendation:
        """Get tariff-based energy recommendation."""
        current = self.get_current_price()
        current_price = current.price_eur_kwh if current else self._fixed_rate
        current_ct = round(current_price * 100, 2)

        optimal = self.find_optimal_window(duration_hours=2)

        if not optimal or optimal.savings_pct < 5:
            return TariffRecommendation(
                action="charge_now",
                reason_de=f"Strompreis aktuell gut ({current_ct} ct/kWh). Jetzt laden/verbrauchen.",
                reason_en=f"Electricity price currently good ({current_ct} ct/kWh). Charge/consume now.",
                current_price_ct=current_ct,
                optimal_price_ct=current_ct,
                savings_pct=0,
                optimal_start="",
                optimal_end="",
            )

        optimal_ct = optimal.avg_price_ct_kwh

        if current and current.level in (PriceLevel.HIGH, PriceLevel.VERY_HIGH):
            action = "wait"
            reason_de = (
                f"Strompreis hoch ({current_ct} ct/kWh). "
                f"Optimal ab {optimal.start[:16]}: {optimal_ct} ct/kWh "
                f"(spare {optimal.savings_pct:.0f}%)."
            )
            reason_en = (
                f"Price high ({current_ct} ct/kWh). "
                f"Optimal from {optimal.start[:16]}: {optimal_ct} ct/kWh "
                f"(save {optimal.savings_pct:.0f}%)."
            )
        elif current and current.level in (PriceLevel.VERY_LOW, PriceLevel.LOW):
            action = "charge_now"
            reason_de = f"Strompreis niedrig ({current_ct} ct/kWh). Jetzt laden!"
            reason_en = f"Price low ({current_ct} ct/kWh). Charge now!"
        else:
            action = "shift"
            reason_de = (
                f"Strompreis normal ({current_ct} ct/kWh). "
                f"Günstiger ab {optimal.start[:16]}: {optimal_ct} ct/kWh."
            )
            reason_en = (
                f"Price normal ({current_ct} ct/kWh). "
                f"Cheaper from {optimal.start[:16]}: {optimal_ct} ct/kWh."
            )

        return TariffRecommendation(
            action=action,
            reason_de=reason_de,
            reason_en=reason_en,
            current_price_ct=current_ct,
            optimal_price_ct=optimal_ct,
            savings_pct=optimal.savings_pct,
            optimal_start=optimal.start,
            optimal_end=optimal.end,
        )

    @property
    def feed_in_rate(self) -> float:
        """Current feed-in tariff."""
        return self._feed_in

    @property
    def cache_valid(self) -> bool:
        """Check if cached prices are still valid."""
        return (time.time() - self._last_updated) < self._cache_ttl

    @property
    def tariff_type(self) -> str:
        """Current tariff type."""
        return self._tariff_type
