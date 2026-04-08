"""Comfort Index — Composite environmental comfort scoring (v5.7.0).

Calculates a 0-100 comfort index from environmental factors:
- Temperature (weight: 35%)
- Humidity (weight: 25%)
- Air quality / CO2 (weight: 20%)
- Light level (weight: 20%)

Also provides adaptive lighting suggestions based on time, weather,
and current light levels.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Weights for comfort factors
WEIGHT_TEMPERATURE = 0.35
WEIGHT_HUMIDITY = 0.25
WEIGHT_AIR_QUALITY = 0.20
WEIGHT_LIGHT = 0.20


@dataclass
class ComfortReading:
    """Single comfort factor reading."""

    factor: str
    raw_value: float | None
    score: float  # 0-100
    weight: float
    status: str  # optimal, good, fair, poor


@dataclass
class ComfortIndex:
    """Composite comfort index result."""

    score: float  # 0-100
    grade: str  # A, B, C, D, F
    readings: list[ComfortReading]
    suggestions: list[str]
    timestamp: str
    zone_id: str | None = None


@dataclass
class LightingSuggestion:
    """Adaptive lighting suggestion."""

    area: str
    current_lux: float | None
    target_lux: float
    brightness_percent: int
    color_temp_kelvin: int
    reason: str


def _temperature_score(temp_c: float | None) -> tuple[float, str]:
    """Score temperature (optimal: 20-22C)."""
    if temp_c is None:
        return 50.0, "unknown"

    # Optimal: 20-22 -> 100
    # Good: 18-24 -> 80
    # Fair: 16-26 -> 60
    # Poor: outside -> drops linearly
    if 20.0 <= temp_c <= 22.0:
        return 100.0, "optimal"
    elif 18.0 <= temp_c <= 24.0:
        dist = min(abs(temp_c - 20.0), abs(temp_c - 22.0))
        return max(80.0, 100.0 - dist * 10), "good"
    elif 16.0 <= temp_c <= 26.0:
        dist = min(abs(temp_c - 18.0), abs(temp_c - 24.0))
        return max(60.0, 80.0 - dist * 10), "fair"
    else:
        # Poor: exponential decay outside comfort range
        if temp_c < 16.0:
            dist = 16.0 - temp_c
        else:
            dist = temp_c - 26.0
        return max(0.0, 60.0 - dist * 8), "poor"


def _humidity_score(humidity_pct: float | None) -> tuple[float, str]:
    """Score humidity (optimal: 40-60%)."""
    if humidity_pct is None:
        return 50.0, "unknown"

    if 40.0 <= humidity_pct <= 60.0:
        return 100.0, "optimal"
    elif 30.0 <= humidity_pct <= 70.0:
        dist = min(abs(humidity_pct - 40.0), abs(humidity_pct - 60.0))
        return max(70.0, 100.0 - dist * 3), "good"
    else:
        if humidity_pct < 30.0:
            dist = 30.0 - humidity_pct
        else:
            dist = humidity_pct - 70.0
        return max(0.0, 70.0 - dist * 3), "fair" if dist < 15 else "poor"


def _air_quality_score(co2_ppm: float | None) -> tuple[float, str]:
    """Score air quality by CO2 concentration (optimal: <800 ppm)."""
    if co2_ppm is None:
        return 50.0, "unknown"

    if co2_ppm <= 600:
        return 100.0, "optimal"
    elif co2_ppm <= 800:
        return 90.0 - (co2_ppm - 600) * 0.05, "good"
    elif co2_ppm <= 1000:
        return 80.0 - (co2_ppm - 800) * 0.1, "fair"
    elif co2_ppm <= 1500:
        return 60.0 - (co2_ppm - 1000) * 0.08, "poor"
    else:
        return max(0.0, 20.0 - (co2_ppm - 1500) * 0.04), "poor"


def _light_score(
    lux: float | None, hour: int
) -> tuple[float, str]:
    """Score light level relative to time of day."""
    if lux is None:
        return 50.0, "unknown"

    # Target lux varies by time of day
    if 6 <= hour <= 9:  # Morning
        target = 300.0
    elif 10 <= hour <= 17:  # Daytime
        target = 500.0
    elif 18 <= hour <= 21:  # Evening
        target = 200.0
    else:  # Night
        target = 50.0

    if target == 0:
        return 100.0 if lux < 10 else 50.0, "optimal" if lux < 10 else "fair"

    ratio = lux / target
    if 0.8 <= ratio <= 1.3:
        return 100.0, "optimal"
    elif 0.5 <= ratio <= 2.0:
        deviation = abs(1.0 - ratio)
        return max(60.0, 100.0 - deviation * 80), "good"
    else:
        deviation = abs(1.0 - ratio)
        return max(0.0, 60.0 - deviation * 40), "fair" if deviation < 2 else "poor"


def _grade_from_score(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 75:
        return "B"
    elif score >= 50:
        return "C"
    elif score >= 40:
        return "D"
    else:
        return "F"


def calculate_comfort_index(
    temperature_c: float | None = None,
    humidity_pct: float | None = None,
    co2_ppm: float | None = None,
    light_lux: float | None = None,
    zone_id: str | None = None,
    hour: int | None = None,
) -> ComfortIndex:
    """Calculate composite comfort index from environmental readings.

    Parameters
    ----------
    temperature_c : float, optional
        Temperature in Celsius.
    humidity_pct : float, optional
        Relative humidity percentage (0-100).
    co2_ppm : float, optional
        CO2 concentration in ppm.
    light_lux : float, optional
        Light level in lux.
    zone_id : str, optional
        Zone/room identifier.
    hour : int, optional
        Hour of day (0-23). Defaults to current UTC hour.
    """
    if hour is None:
        hour = datetime.now(timezone.utc).hour

    temp_score, temp_status = _temperature_score(temperature_c)
    hum_score, hum_status = _humidity_score(humidity_pct)
    aq_score, aq_status = _air_quality_score(co2_ppm)
    light_sc, light_status = _light_score(light_lux, hour)

    readings = [
        ComfortReading("temperature", temperature_c, temp_score, WEIGHT_TEMPERATURE, temp_status),
        ComfortReading("humidity", humidity_pct, hum_score, WEIGHT_HUMIDITY, hum_status),
        ComfortReading("air_quality", co2_ppm, aq_score, WEIGHT_AIR_QUALITY, aq_status),
        ComfortReading("light", light_lux, light_sc, WEIGHT_LIGHT, light_status),
    ]

    # Weighted average
    total_weight = sum(r.weight for r in readings)
    composite = sum(r.score * r.weight for r in readings) / total_weight

    # Generate suggestions
    suggestions = _generate_suggestions(readings, temperature_c, humidity_pct, co2_ppm, light_lux, hour)

    return ComfortIndex(
        score=round(composite, 1),
        grade=_grade_from_score(composite),
        readings=readings,
        suggestions=suggestions,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        zone_id=zone_id,
    )


def _generate_suggestions(
    readings: list[ComfortReading],
    temp: float | None,
    humidity: float | None,
    co2: float | None,
    lux: float | None,
    hour: int,
) -> list[str]:
    """Generate improvement suggestions based on readings."""
    suggestions: list[str] = []

    for r in readings:
        if r.status == "poor":
            if r.factor == "temperature":
                if temp is not None:
                    if temp < 18:
                        suggestions.append("Heizung hoeher stellen — Temperatur zu niedrig")
                    else:
                        suggestions.append("Klimaanlage einschalten oder lueften — Temperatur zu hoch")
            elif r.factor == "humidity":
                if humidity is not None:
                    if humidity < 30:
                        suggestions.append("Luftbefeuchter einschalten — Luft zu trocken")
                    else:
                        suggestions.append("Lueften oder Entfeuchter einschalten — Luft zu feucht")
            elif r.factor == "air_quality":
                suggestions.append("Fenster oeffnen — CO2-Wert zu hoch")
            elif r.factor == "light":
                if lux is not None and lux < 100 and 8 <= hour <= 20:
                    suggestions.append("Beleuchtung erhoehen — zu dunkel fuer die Tageszeit")
                elif lux is not None and lux > 800 and hour >= 21:
                    suggestions.append("Beleuchtung dimmen — zu hell fuer den Abend")
        elif r.status == "fair":
            if r.factor == "air_quality" and co2 is not None and co2 > 1000:
                suggestions.append("Bald lueften — CO2-Wert steigt")

    return suggestions


def get_lighting_suggestion(
    current_lux: float | None = None,
    hour: int | None = None,
    cloud_cover_pct: float = 50.0,
    area: str = "Wohnzimmer",
) -> LightingSuggestion:
    """Generate adaptive lighting suggestion for area.

    Parameters
    ----------
    current_lux : float, optional
        Current measured light level.
    hour : int, optional
        Hour of day (0-23). Defaults to current UTC hour.
    cloud_cover_pct : float
        Cloud cover percentage (0-100) affecting natural light.
    area : str
        Room/area name.
    """
    if hour is None:
        hour = datetime.now(timezone.utc).hour

    # Target lux by time
    if 6 <= hour <= 8:
        target_lux = 250.0
        color_temp = 4000  # Neutral white (wake up)
        reason = "Aufwachphase — neutrales Licht"
    elif 9 <= hour <= 11:
        target_lux = 500.0
        color_temp = 5000  # Cool white (productive)
        reason = "Vormittag — produktives Arbeitslicht"
    elif 12 <= hour <= 17:
        target_lux = 500.0
        color_temp = 4500  # Daylight
        reason = "Tageslicht-Ergaenzung"
    elif 18 <= hour <= 20:
        target_lux = 200.0
        color_temp = 3000  # Warm white (evening)
        reason = "Abendstimmung — warmes Licht"
    elif 21 <= hour <= 23:
        target_lux = 80.0
        color_temp = 2700  # Very warm (wind down)
        reason = "Entspannung — gedimmtes Warmweiss"
    else:
        target_lux = 20.0
        color_temp = 2200  # Candlelight (night)
        reason = "Nachtlicht — minimale Helligkeit"

    # Adjust for cloud cover (more artificial light needed on cloudy days)
    if 8 <= hour <= 18:
        cloud_factor = 1.0 + (cloud_cover_pct / 200.0)  # 1.0 - 1.5x
        target_lux *= cloud_factor

    # Calculate brightness percentage (0-100)
    if current_lux is not None and current_lux >= target_lux:
        brightness = 0  # No artificial light needed
        reason = "Genuegend Tageslicht — keine Beleuchtung noetig"
    else:
        deficit = target_lux - (current_lux or 0)
        brightness = min(100, max(5, int(deficit / target_lux * 100)))

    return LightingSuggestion(
        area=area,
        current_lux=current_lux,
        target_lux=round(target_lux, 0),
        brightness_percent=brightness,
        color_temp_kelvin=color_temp,
        reason=reason,
    )
