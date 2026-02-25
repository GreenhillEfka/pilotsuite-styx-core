"""Regional Context Provider — Zero-config location-aware data (v5.15.0).

Pulls location from Home Assistant's zone.home entity and derives all
regional context: solar position, timezone, country, electricity pricing
defaults, weather service endpoints, and news sources.

Design: Zero-config — user just installs PilotSuite, and the system
automatically adapts to their region (DE/AT/CH primarily).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta, timezone
from typing import Optional


# ── Data classes ────────────────────────────────────────────────────────────

@dataclass
class Location:
    """Home location from HA zone.home."""

    latitude: float
    longitude: float
    elevation_m: float
    timezone: str
    country_code: str  # DE, AT, CH, etc.
    region: str  # Bundesland / Kanton


@dataclass
class SolarPosition:
    """Current solar position at location."""

    timestamp: str
    sunrise: str
    sunset: str
    solar_noon: str
    day_length_hours: float
    elevation_deg: float  # current sun elevation
    azimuth_deg: float  # current sun azimuth
    is_daylight: bool


@dataclass
class RegionalDefaults:
    """Region-specific defaults for zero-config."""

    grid_price_eur_kwh: float
    feed_in_tariff_eur_kwh: float
    price_api: str  # "awattar_de", "awattar_at", "epex_ch"
    weather_service: str  # "dwd", "zamg", "meteoschweiz"
    warning_service: str  # URL for weather warnings
    news_sources: list[str]
    currency: str
    language: str
    pv_optimal_tilt_deg: float
    pv_optimal_azimuth_deg: float  # 180 = south
    heating_degree_base_c: float


@dataclass
class RegionalContext:
    """Complete regional context bundle."""

    location: dict
    solar: dict
    defaults: dict
    generated_at: str


# ── Country/Region databases ───────────────────────────────────────────────

_COUNTRY_DEFAULTS: dict[str, dict] = {
    "DE": {
        "grid_price_eur_kwh": 0.30,
        "feed_in_tariff_eur_kwh": 0.082,
        "price_api": "awattar_de",
        "weather_service": "dwd",
        "warning_service": "https://www.dwd.de/DWD/warnungen/warnapp/json/warnings.json",
        "news_sources": ["tagesschau", "spiegel", "zeit"],
        "currency": "EUR",
        "language": "de",
        "pv_optimal_tilt_deg": 35.0,
        "pv_optimal_azimuth_deg": 180.0,
        "heating_degree_base_c": 15.0,
    },
    "AT": {
        "grid_price_eur_kwh": 0.25,
        "feed_in_tariff_eur_kwh": 0.076,
        "price_api": "awattar_at",
        "weather_service": "zamg",
        "warning_service": "https://warnungen.zamg.ac.at/wsapp/api/getWarnings",
        "news_sources": ["orf", "derstandard", "kurier"],
        "currency": "EUR",
        "language": "de",
        "pv_optimal_tilt_deg": 33.0,
        "pv_optimal_azimuth_deg": 180.0,
        "heating_degree_base_c": 15.0,
    },
    "CH": {
        "grid_price_eur_kwh": 0.27,
        "feed_in_tariff_eur_kwh": 0.0,
        "price_api": "epex_ch",
        "weather_service": "meteoschweiz",
        "warning_service": "https://www.meteoschweiz.admin.ch/warn/api/v1/warnings",
        "news_sources": ["srf", "nzz", "blick"],
        "currency": "CHF",
        "language": "de",
        "pv_optimal_tilt_deg": 34.0,
        "pv_optimal_azimuth_deg": 180.0,
        "heating_degree_base_c": 15.0,
    },
}

# Latitude → country rough mapping for DACH region
_LAT_LON_COUNTRY = [
    # (lat_min, lat_max, lon_min, lon_max, country)
    (46.0, 48.5, 5.9, 10.5, "CH"),
    (46.3, 49.0, 9.5, 17.2, "AT"),
    (47.0, 55.1, 5.8, 15.1, "DE"),
]

# German Bundesland from approximate coordinates
_BUNDESLAENDER = [
    (53.5, 55.1, 8.0, 11.5, "Schleswig-Holstein"),
    (53.0, 54.0, 8.5, 12.0, "Hamburg/Niedersachsen"),
    (52.0, 53.5, 6.5, 11.5, "Niedersachsen"),
    (53.0, 53.7, 8.7, 8.9, "Bremen"),
    (51.5, 53.0, 6.0, 8.0, "Nordrhein-Westfalen"),
    (50.0, 51.5, 7.5, 10.5, "Hessen"),
    (49.0, 50.5, 6.0, 8.5, "Rheinland-Pfalz/Saarland"),
    (47.5, 49.5, 7.5, 10.5, "Baden-Wuerttemberg"),
    (47.0, 49.0, 10.0, 13.9, "Bayern"),
    (50.5, 52.0, 9.5, 13.0, "Thueringen"),
    (51.0, 52.5, 11.0, 15.1, "Sachsen-Anhalt/Sachsen"),
    (52.0, 54.0, 11.5, 14.5, "Brandenburg/Berlin"),
    (53.5, 54.7, 11.0, 14.5, "Mecklenburg-Vorpommern"),
]


# ── Solar calculations (simplified, no external deps) ──────────────────────

def _julian_day(dt: datetime) -> float:
    """Julian day number."""
    a = (14 - dt.month) // 12
    y = dt.year + 4800 - a
    m = dt.month + 12 * a - 3
    return dt.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def _solar_declination(day_of_year: int) -> float:
    """Solar declination in radians."""
    return math.radians(-23.45 * math.cos(math.radians(360 / 365 * (day_of_year + 10))))


def _equation_of_time(day_of_year: int) -> float:
    """Equation of time in minutes."""
    b = math.radians(360 / 365 * (day_of_year - 81))
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def _hour_angle_sunrise(lat_rad: float, decl: float) -> float:
    """Hour angle at sunrise in radians."""
    cos_ha = -math.tan(lat_rad) * math.tan(decl)
    cos_ha = max(-1.0, min(1.0, cos_ha))
    return math.acos(cos_ha)


def calculate_solar_position(
    latitude: float,
    longitude: float,
    dt: datetime | None = None,
    tz_offset_hours: float = 1.0,
) -> SolarPosition:
    """Calculate solar position for given location and time."""
    if dt is None:
        dt = datetime.now()

    doy = dt.timetuple().tm_yday
    lat_rad = math.radians(latitude)
    decl = _solar_declination(doy)
    eot = _equation_of_time(doy)

    # Solar noon (local time)
    solar_noon_minutes = 720 - 4 * longitude - eot + tz_offset_hours * 60
    solar_noon_h = solar_noon_minutes / 60.0

    # Sunrise/sunset
    ha_sunrise = _hour_angle_sunrise(lat_rad, decl)
    day_length_h = 2 * math.degrees(ha_sunrise) / 15.0

    sunrise_h = solar_noon_h - day_length_h / 2
    sunset_h = solar_noon_h + day_length_h / 2

    # Current hour as decimal
    current_h = dt.hour + dt.minute / 60.0

    # Solar elevation
    hour_angle = math.radians(15 * (current_h - solar_noon_h))
    sin_elev = (
        math.sin(lat_rad) * math.sin(decl)
        + math.cos(lat_rad) * math.cos(decl) * math.cos(hour_angle)
    )
    elevation = math.degrees(math.asin(max(-1, min(1, sin_elev))))

    # Solar azimuth
    cos_az = (
        math.sin(decl) - math.sin(lat_rad) * sin_elev
    ) / (math.cos(lat_rad) * math.cos(math.radians(elevation)) + 1e-10)
    cos_az = max(-1, min(1, cos_az))
    azimuth = math.degrees(math.acos(cos_az))
    if hour_angle > 0:
        azimuth = 360 - azimuth

    def _h_to_time(h: float) -> str:
        hh = int(h) % 24
        mm = int((h - int(h)) * 60)
        return f"{hh:02d}:{mm:02d}"

    return SolarPosition(
        timestamp=dt.isoformat(),
        sunrise=_h_to_time(sunrise_h),
        sunset=_h_to_time(sunset_h),
        solar_noon=_h_to_time(solar_noon_h),
        day_length_hours=round(day_length_h, 2),
        elevation_deg=round(elevation, 1),
        azimuth_deg=round(azimuth, 1),
        is_daylight=sunrise_h <= current_h <= sunset_h,
    )


# ── Country detection ───────────────────────────────────────────────────────

def detect_country(lat: float, lon: float) -> str:
    """Detect country from coordinates (DACH region)."""
    # First pass: Switzerland is geographically well-separated in this model.
    ch_box = next((b for b in _LAT_LON_COUNTRY if b[4] == "CH"), None)
    de_box = next((b for b in _LAT_LON_COUNTRY if b[4] == "DE"), None)
    at_box = next((b for b in _LAT_LON_COUNTRY if b[4] == "AT"), None)

    if ch_box and ch_box[0] <= lat <= ch_box[1] and ch_box[2] <= lon <= ch_box[3]:
        return "CH"

    in_de = bool(de_box and de_box[0] <= lat <= de_box[1] and de_box[2] <= lon <= de_box[3])
    in_at = bool(at_box and at_box[0] <= lat <= at_box[1] and at_box[2] <= lon <= at_box[3])

    if in_de and in_at:
        # DE/AT overlap handling (rough Alpine border approximation):
        # - Eastern overlap is mostly AT
        # - Western overlap split by latitude to keep Munich in DE and Tirol in AT
        if lon >= 14.0:
            return "AT"
        if lon < 12.5:
            return "DE" if lat >= 47.8 else "AT"
        return "DE" if lat >= 48.0 else "AT"
    if in_de:
        return "DE"
    if in_at:
        return "AT"
    return "DE"  # Default


def detect_region(lat: float, lon: float, country: str) -> str:
    """Detect region/Bundesland from coordinates."""
    if country == "DE":
        for lat_min, lat_max, lon_min, lon_max, region in _BUNDESLAENDER:
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                return region
    elif country == "AT":
        if lon >= 15.0:
            return "Wien/Niederoesterreich"
        if lat > 47.5 and lon < 13:
            return "Tirol/Vorarlberg"
        if lat > 47.5:
            return "Salzburg/Kaernten"
        return "Steiermark/Burgenland"
    elif country == "CH":
        if lon < 7.5:
            return "Westschweiz"
        if lon > 9.0:
            return "Ostschweiz"
        return "Mittelland"
    return "Unbekannt"


# ── Main Provider ───────────────────────────────────────────────────────────

class RegionalContextProvider:
    """Provides zero-config regional context from HA location."""

    def __init__(
        self,
        latitude: float = 51.1657,  # Germany center default
        longitude: float = 10.4515,
        elevation_m: float = 200.0,
        timezone: str = "Europe/Berlin",
    ):
        self._lat = latitude
        self._lon = longitude
        self._elev = elevation_m
        self._tz = timezone
        self._country = detect_country(latitude, longitude)
        self._region = detect_region(latitude, longitude, self._country)

    @property
    def location(self) -> Location:
        return Location(
            latitude=self._lat,
            longitude=self._lon,
            elevation_m=self._elev,
            timezone=self._tz,
            country_code=self._country,
            region=self._region,
        )

    @property
    def defaults(self) -> RegionalDefaults:
        d = _COUNTRY_DEFAULTS.get(self._country, _COUNTRY_DEFAULTS["DE"])
        return RegionalDefaults(**d)

    def get_solar_position(self, dt: datetime | None = None) -> SolarPosition:
        """Get current solar position."""
        tz_offset = 1.0  # CET
        now = dt or datetime.now()
        # Simple DST check for Central Europe
        if 3 <= now.month <= 10:
            tz_offset = 2.0
        return calculate_solar_position(self._lat, self._lon, now, tz_offset)

    def get_context(self) -> RegionalContext:
        """Get complete regional context bundle."""
        solar = self.get_solar_position()
        return RegionalContext(
            location=asdict(self.location),
            solar=asdict(solar),
            defaults=asdict(self.defaults),
            generated_at=datetime.now().isoformat(),
        )

    def get_pv_factor(self, dt: datetime | None = None) -> float:
        """Get current PV production factor (0-1) based on solar position."""
        solar = self.get_solar_position(dt)
        if not solar.is_daylight or solar.elevation_deg <= 0:
            return 0.0
        # Normalize: max elevation ~60° in summer Central Europe
        return round(min(solar.elevation_deg / 60.0, 1.0), 3)

    def get_day_info(self, target_date: date | None = None) -> dict:
        """Get day information for a specific date."""
        d = target_date or date.today()
        dt = datetime(d.year, d.month, d.day, 12, 0)
        solar = self.get_solar_position(dt)
        defaults = self.defaults

        return {
            "date": d.isoformat(),
            "country": self._country,
            "region": self._region,
            "sunrise": solar.sunrise,
            "sunset": solar.sunset,
            "day_length_hours": solar.day_length_hours,
            "solar_noon": solar.solar_noon,
            "grid_price_eur_kwh": defaults.grid_price_eur_kwh,
            "feed_in_tariff_eur_kwh": defaults.feed_in_tariff_eur_kwh,
            "weather_service": defaults.weather_service,
            "language": defaults.language,
        }

    def update_location(
        self,
        latitude: float,
        longitude: float,
        elevation_m: float = 200.0,
        timezone: str = "Europe/Berlin",
    ) -> None:
        """Update location (e.g., from HA zone.home)."""
        self._lat = latitude
        self._lon = longitude
        self._elev = elevation_m
        self._tz = timezone
        self._country = detect_country(latitude, longitude)
        self._region = detect_region(latitude, longitude, self._country)
