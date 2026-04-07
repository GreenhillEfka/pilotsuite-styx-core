"""Fuel Price Tracker with Tankerkoenig integration (v5.17.0).

Tracks Benzin/Diesel/E10 prices from Tankerkoenig API and compares
cost per 100km between electric (Strom), Diesel, Benzin, and E10.
Zero-config: uses HA location for nearest station lookup.

Tankerkoenig API: https://creativecommons.tankerkoenig.de/
Free API with region-based station search (no HA addon required).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class FuelStation:
    """A fuel station from Tankerkoenig."""

    id: str
    name: str
    brand: str
    street: str
    place: str
    lat: float
    lng: float
    dist: float  # km from home
    diesel: Optional[float]
    e5: Optional[float]  # Super/Benzin
    e10: Optional[float]
    is_open: bool


@dataclass
class FuelPrices:
    """Current fuel prices summary."""

    diesel_avg: Optional[float]
    diesel_min: Optional[float]
    diesel_max: Optional[float]
    e5_avg: Optional[float]
    e5_min: Optional[float]
    e5_max: Optional[float]
    e10_avg: Optional[float]
    e10_min: Optional[float]
    e10_max: Optional[float]
    station_count: int
    cheapest_diesel: Optional[str]  # station name
    cheapest_e5: Optional[str]
    cheapest_e10: Optional[str]
    radius_km: float
    updated_at: str


@dataclass
class CostPer100km:
    """Cost comparison per 100km for different fuel types."""

    electric_eur: float
    diesel_eur: float
    benzin_eur: float  # E5/Super
    e10_eur: float
    cheapest: str  # "electric", "diesel", "benzin", "e10"
    savings_vs_diesel_eur: float  # savings of cheapest vs diesel
    savings_vs_benzin_eur: float
    co2_electric_kg: float
    co2_diesel_kg: float
    co2_benzin_kg: float


@dataclass
class FuelDashboardData:
    """Dashboard-ready fuel price data."""

    prices: dict
    cost_per_100km: dict
    stations: list[dict]
    price_history: list[dict]  # last N price snapshots
    recommendation_de: str
    recommendation_en: str
    updated_at: str


# ── Default consumption values ───────────────────────────────────────────

# Average consumption per 100km
_DEFAULTS = {
    "ev_kwh_per_100km": 18.0,       # Average EV: 18 kWh/100km
    "diesel_l_per_100km": 6.0,       # Average diesel car
    "benzin_l_per_100km": 7.5,       # Average petrol car
    "e10_l_per_100km": 7.5,          # Same as benzin (E10 ~same consumption)
    "grid_price_eur_kwh": 0.30,      # German average grid price
    # CO2 emissions per 100km (kg)
    "co2_electric_kg_per_100km": 5.0,   # German grid mix ~280g/kWh * 18kWh
    "co2_diesel_kg_per_100km": 15.9,    # 2.65 kg/L * 6L
    "co2_benzin_kg_per_100km": 17.4,    # 2.32 kg/L * 7.5L
}


# ── Main Fuel Price Tracker ──────────────────────────────────────────────

class FuelPriceTracker:
    """Tracks fuel prices and compares with electricity costs.

    Uses Tankerkoenig API for fuel prices and regional context
    for electricity prices. Provides cost-per-100km comparison.
    """

    def __init__(
        self,
        latitude: float = 51.1657,
        longitude: float = 10.4515,
        radius_km: float = 10.0,
        grid_price_eur_kwh: float = 0.30,
    ):
        self._lat = latitude
        self._lon = longitude
        self._radius = radius_km
        self._grid_price = grid_price_eur_kwh

        # Customizable consumption values
        self._ev_kwh = _DEFAULTS["ev_kwh_per_100km"]
        self._diesel_l = _DEFAULTS["diesel_l_per_100km"]
        self._benzin_l = _DEFAULTS["benzin_l_per_100km"]
        self._e10_l = _DEFAULTS["e10_l_per_100km"]

        # State
        self._stations: list[FuelStation] = []
        self._price_history: list[dict] = []
        self._max_history: int = 168  # 1 week at hourly intervals
        self._last_updated: float = 0
        self._cache_ttl: float = 600  # 10 minutes
        self._api_key: str = ""

    def set_api_key(self, key: str) -> None:
        """Set Tankerkoenig API key."""
        self._api_key = key

    def update_location(
        self, latitude: float, longitude: float, radius_km: float = 10.0
    ) -> None:
        """Update search location."""
        self._lat = latitude
        self._lon = longitude
        self._radius = radius_km

    def update_grid_price(self, price_eur_kwh: float) -> None:
        """Update electricity grid price for comparison."""
        self._grid_price = price_eur_kwh

    def update_consumption(
        self,
        ev_kwh: float | None = None,
        diesel_l: float | None = None,
        benzin_l: float | None = None,
        e10_l: float | None = None,
    ) -> None:
        """Update vehicle consumption values."""
        if ev_kwh is not None:
            self._ev_kwh = ev_kwh
        if diesel_l is not None:
            self._diesel_l = diesel_l
        if benzin_l is not None:
            self._benzin_l = benzin_l
        if e10_l is not None:
            self._e10_l = e10_l

    def get_api_url(self) -> str:
        """Get Tankerkoenig API URL for current location."""
        return (
            f"https://creativecommons.tankerkoenig.de/json/list.php"
            f"?lat={self._lat}&lng={self._lon}&rad={self._radius}"
            f"&sort=price&type=all&apikey={self._api_key}"
        )

    def process_tankerkoenig_response(self, data: dict) -> list[FuelStation]:
        """Parse Tankerkoenig API response into FuelStation list."""
        if not data.get("ok"):
            logger.warning("Tankerkoenig API error: %s", data.get("message", "Unknown"))
            return []

        stations = []
        for s in data.get("stations", []):
            try:
                station = FuelStation(
                    id=s.get("id", ""),
                    name=s.get("name", "Unbekannt"),
                    brand=s.get("brand", ""),
                    street=s.get("street", ""),
                    place=s.get("place", ""),
                    lat=float(s.get("lat", 0)),
                    lng=float(s.get("lng", 0)),
                    dist=float(s.get("dist", 0)),
                    diesel=s.get("diesel"),
                    e5=s.get("e5"),
                    e10=s.get("e10"),
                    is_open=s.get("isOpen", False),
                )
                stations.append(station)
            except Exception as exc:
                logger.debug("Failed to parse station: %s", exc)

        self._stations = stations
        self._last_updated = time.time()

        # Record price snapshot
        prices = self.get_prices()
        if prices:
            self._price_history.append({
                "timestamp": datetime.now().isoformat(),
                "diesel_avg": prices.diesel_avg,
                "e5_avg": prices.e5_avg,
                "e10_avg": prices.e10_avg,
            })
            # Trim history
            if len(self._price_history) > self._max_history:
                self._price_history = self._price_history[-self._max_history:]

        return stations

    def process_manual_prices(
        self,
        diesel: float | None = None,
        e5: float | None = None,
        e10: float | None = None,
    ) -> list[FuelStation]:
        """Set prices manually (for users without Tankerkoenig API key)."""
        station = FuelStation(
            id="manual",
            name="Manuell eingetragen",
            brand="Manual",
            street="",
            place="",
            lat=self._lat,
            lng=self._lon,
            dist=0.0,
            diesel=diesel,
            e5=e5,
            e10=e10,
            is_open=True,
        )
        self._stations = [station]
        self._last_updated = time.time()

        # Record snapshot
        self._price_history.append({
            "timestamp": datetime.now().isoformat(),
            "diesel_avg": diesel,
            "e5_avg": e5,
            "e10_avg": e10,
        })
        if len(self._price_history) > self._max_history:
            self._price_history = self._price_history[-self._max_history:]

        return [station]

    def get_prices(self) -> FuelPrices | None:
        """Get aggregated fuel price summary."""
        open_stations = [s for s in self._stations if s.is_open]
        if not open_stations:
            return None

        def _stats(values: list[float]) -> tuple[float | None, float | None, float | None]:
            if not values:
                return None, None, None
            return (
                round(sum(values) / len(values), 3),
                round(min(values), 3),
                round(max(values), 3),
            )

        diesel_vals = [s.diesel for s in open_stations if s.diesel is not None]
        e5_vals = [s.e5 for s in open_stations if s.e5 is not None]
        e10_vals = [s.e10 for s in open_stations if s.e10 is not None]

        d_avg, d_min, d_max = _stats(diesel_vals)
        e5_avg, e5_min, e5_max = _stats(e5_vals)
        e10_avg, e10_min, e10_max = _stats(e10_vals)

        # Find cheapest stations
        cheapest_diesel = None
        cheapest_e5 = None
        cheapest_e10 = None

        if diesel_vals:
            min_d = min(diesel_vals)
            for s in open_stations:
                if s.diesel == min_d:
                    cheapest_diesel = f"{s.name} ({s.place})"
                    break

        if e5_vals:
            min_e5 = min(e5_vals)
            for s in open_stations:
                if s.e5 == min_e5:
                    cheapest_e5 = f"{s.name} ({s.place})"
                    break

        if e10_vals:
            min_e10 = min(e10_vals)
            for s in open_stations:
                if s.e10 == min_e10:
                    cheapest_e10 = f"{s.name} ({s.place})"
                    break

        return FuelPrices(
            diesel_avg=d_avg,
            diesel_min=d_min,
            diesel_max=d_max,
            e5_avg=e5_avg,
            e5_min=e5_min,
            e5_max=e5_max,
            e10_avg=e10_avg,
            e10_min=e10_min,
            e10_max=e10_max,
            station_count=len(open_stations),
            cheapest_diesel=cheapest_diesel,
            cheapest_e5=cheapest_e5,
            cheapest_e10=cheapest_e10,
            radius_km=self._radius,
            updated_at=datetime.fromtimestamp(self._last_updated).isoformat()
            if self._last_updated
            else "",
        )

    def get_cost_per_100km(self) -> CostPer100km | None:
        """Calculate cost per 100km for all fuel types vs electric."""
        prices = self.get_prices()
        if not prices:
            return None

        # Electric cost
        electric_cost = round(self._ev_kwh * self._grid_price, 2)

        # Fuel costs (use average price, fallback to 0)
        diesel_cost = round(self._diesel_l * (prices.diesel_avg or 0), 2)
        benzin_cost = round(self._benzin_l * (prices.e5_avg or 0), 2)
        e10_cost = round(self._e10_l * (prices.e10_avg or 0), 2)

        # Find cheapest
        options = {
            "electric": electric_cost,
            "diesel": diesel_cost,
            "benzin": benzin_cost,
            "e10": e10_cost,
        }
        # Filter out zero-cost options (no price available)
        valid = {k: v for k, v in options.items() if v > 0}
        cheapest = min(valid, key=valid.get) if valid else "electric"

        return CostPer100km(
            electric_eur=electric_cost,
            diesel_eur=diesel_cost,
            benzin_eur=benzin_cost,
            e10_eur=e10_cost,
            cheapest=cheapest,
            savings_vs_diesel_eur=round(diesel_cost - electric_cost, 2)
            if diesel_cost > 0
            else 0.0,
            savings_vs_benzin_eur=round(benzin_cost - electric_cost, 2)
            if benzin_cost > 0
            else 0.0,
            co2_electric_kg=round(
                _DEFAULTS["co2_electric_kg_per_100km"], 1
            ),
            co2_diesel_kg=round(
                _DEFAULTS["co2_diesel_kg_per_100km"], 1
            ),
            co2_benzin_kg=round(
                _DEFAULTS["co2_benzin_kg_per_100km"], 1
            ),
        )

    def get_dashboard_data(self) -> FuelDashboardData:
        """Get dashboard-ready data with all comparisons."""
        prices = self.get_prices()
        cost = self.get_cost_per_100km()

        # Recommendations
        rec_de = self._recommendation_de(cost)
        rec_en = self._recommendation_en(cost)

        # Top 5 nearest open stations
        open_sorted = sorted(
            [s for s in self._stations if s.is_open],
            key=lambda s: s.dist,
        )[:5]

        return FuelDashboardData(
            prices=asdict(prices) if prices else {},
            cost_per_100km=asdict(cost) if cost else {},
            stations=[asdict(s) for s in open_sorted],
            price_history=list(self._price_history[-48:]),  # last 48 snapshots
            recommendation_de=rec_de,
            recommendation_en=rec_en,
            updated_at=datetime.fromtimestamp(self._last_updated).isoformat()
            if self._last_updated
            else "",
        )

    def _recommendation_de(self, cost: CostPer100km | None) -> str:
        """Generate German recommendation."""
        if not cost:
            return "Keine Preisdaten verfügbar."

        if cost.cheapest == "electric":
            savings = max(cost.savings_vs_diesel_eur, cost.savings_vs_benzin_eur)
            return (
                f"Elektro ist am günstigsten: {cost.electric_eur:.2f} EUR/100km. "
                f"Ersparnis bis zu {savings:.2f} EUR/100km gegenüber Verbrenner. "
                f"CO₂-Einsparung: {cost.co2_benzin_kg - cost.co2_electric_kg:.1f} kg/100km."
            )
        elif cost.cheapest == "diesel":
            diff = cost.electric_eur - cost.diesel_eur
            return (
                f"Diesel aktuell günstiger: {cost.diesel_eur:.2f} EUR/100km "
                f"vs. Strom {cost.electric_eur:.2f} EUR/100km "
                f"(+{diff:.2f} EUR). Aber: {cost.co2_diesel_kg - cost.co2_electric_kg:.1f} kg "
                f"mehr CO₂/100km."
            )
        elif cost.cheapest == "e10":
            return (
                f"E10 aktuell am günstigsten: {cost.e10_eur:.2f} EUR/100km. "
                f"Strom: {cost.electric_eur:.2f} EUR/100km. "
                f"CO₂-Vorteil Strom: {cost.co2_benzin_kg - cost.co2_electric_kg:.1f} kg/100km."
            )
        else:
            return (
                f"Benzin (Super): {cost.benzin_eur:.2f} EUR/100km. "
                f"Strom: {cost.electric_eur:.2f} EUR/100km."
            )

    def _recommendation_en(self, cost: CostPer100km | None) -> str:
        """Generate English recommendation."""
        if not cost:
            return "No price data available."

        if cost.cheapest == "electric":
            savings = max(cost.savings_vs_diesel_eur, cost.savings_vs_benzin_eur)
            return (
                f"Electric is cheapest: {cost.electric_eur:.2f} EUR/100km. "
                f"Save up to {savings:.2f} EUR/100km vs combustion. "
                f"CO₂ savings: {cost.co2_benzin_kg - cost.co2_electric_kg:.1f} kg/100km."
            )
        elif cost.cheapest == "diesel":
            return (
                f"Diesel currently cheaper: {cost.diesel_eur:.2f} EUR/100km "
                f"vs electric {cost.electric_eur:.2f} EUR/100km. "
                f"But: {cost.co2_diesel_kg - cost.co2_electric_kg:.1f} kg more CO₂/100km."
            )
        elif cost.cheapest == "e10":
            return (
                f"E10 currently cheapest: {cost.e10_eur:.2f} EUR/100km. "
                f"Electric: {cost.electric_eur:.2f} EUR/100km."
            )
        else:
            return (
                f"Petrol (Super): {cost.benzin_eur:.2f} EUR/100km. "
                f"Electric: {cost.electric_eur:.2f} EUR/100km."
            )

    @property
    def cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        return (time.time() - self._last_updated) < self._cache_ttl

    @property
    def station_count(self) -> int:
        """Number of tracked stations."""
        return len([s for s in self._stations if s.is_open])

    @property
    def has_api_key(self) -> bool:
        """Check if API key is configured."""
        return bool(self._api_key)
