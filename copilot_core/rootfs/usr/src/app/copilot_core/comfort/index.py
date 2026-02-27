"""Comfort Index — Composite environmental comfort scoring (v6.0.0).

Calculates a 0-100 comfort index from environmental factors using
scientifically grounded scoring models:

- Temperature (weight: 30%) — Gaussian bell curve centered on 21C (ISO 7730)
- Humidity (weight: 20%) — Gaussian bell curve centered on 50% (ASHRAE 55)
- Thermal interaction (weight: 10%) — Heat index penalty (Steadman model)
- Air quality / CO2 (weight: 20%) — Sigmoid decay (WHO guidelines)
- Light level (weight: 20%) — Circadian-aware Gaussian scoring

References:
- ISO 7730: Ergonomics of the thermal environment (PMV/PPD)
- ASHRAE Standard 55: Thermal Environmental Conditions
- Steadman (1979): Heat index model
- WHO: Indoor air quality guidelines (CO2)
- CIE: Circadian stimulus model for lighting
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Weights for comfort factors (sum = 1.0)
WEIGHT_TEMPERATURE = 0.30
WEIGHT_HUMIDITY = 0.20
WEIGHT_THERMAL_INTERACTION = 0.10
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


def _gaussian_score(value: float, optimal: float, sigma: float) -> float:
    """Gaussian bell curve scoring: 100 at optimal, decays with distance.

    score = 100 * exp(-0.5 * ((value - optimal) / sigma)^2)

    This provides smooth, continuous scoring without discontinuities.
    sigma controls the width of the comfort band.
    """
    z = (value - optimal) / sigma
    return 100.0 * math.exp(-0.5 * z * z)


def _plateau_gaussian_score(
    value: float, low: float, high: float, sigma: float
) -> float:
    """Gaussian with a flat optimal plateau between low and high.

    Returns 100 within [low, high], decays as Gaussian outside.
    """
    if low <= value <= high:
        return 100.0
    if value < low:
        return _gaussian_score(value, low, sigma)
    return _gaussian_score(value, high, sigma)


def _status_from_score(score: float) -> str:
    """Derive status label from numeric score."""
    if score >= 85:
        return "optimal"
    if score >= 65:
        return "good"
    if score >= 40:
        return "fair"
    return "poor"


def _temperature_score(temp_c: float | None) -> tuple[float, str]:
    """Score temperature using ISO 7730-inspired Gaussian model.

    Optimal band: 20-22C (PMV ≈ 0 for typical clothing/activity).
    sigma = 3.0C: score drops to ~60 at ±3C from optimal edges.
    """
    if temp_c is None:
        return 50.0, "unknown"

    score = _plateau_gaussian_score(temp_c, 20.0, 22.0, sigma=3.0)
    return round(score, 1), _status_from_score(score)


def _humidity_score(humidity_pct: float | None) -> tuple[float, str]:
    """Score humidity using ASHRAE 55-inspired Gaussian model.

    Optimal band: 40-60% RH.
    sigma = 15.0: score drops to ~60 at 25% or 75% RH.
    """
    if humidity_pct is None:
        return 50.0, "unknown"

    score = _plateau_gaussian_score(humidity_pct, 40.0, 60.0, sigma=15.0)
    return round(score, 1), _status_from_score(score)


def _heat_index_penalty(
    temp_c: float | None, humidity_pct: float | None
) -> tuple[float, str]:
    """Compute thermal interaction penalty using simplified Steadman model.

    The heat index captures the synergistic discomfort of high temperature
    AND high humidity. Returns a score 0-100 where 100 = no penalty.

    Based on Steadman (1979) simplified regression:
    HI = -8.785 + 1.611*T + 2.339*RH - 0.146*T*RH (for T>20, RH>40)
    """
    if temp_c is None or humidity_pct is None:
        return 100.0, "unknown"

    # Only penalize when both are elevated
    if temp_c <= 22.0 or humidity_pct <= 40.0:
        return 100.0, "optimal"

    # Simplified heat index deviation from actual temperature
    # Positive HI_excess means "feels hotter than it is"
    hi_excess = 0.0
    if temp_c > 22.0 and humidity_pct > 40.0:
        # Interaction term: each 10% RH above 40% adds ~0.5C perceived
        rh_excess = (humidity_pct - 40.0) / 10.0
        temp_excess = temp_c - 22.0
        hi_excess = temp_excess * rh_excess * 0.15

    # Score: 100 at no excess, sigmoid decay for discomfort
    # sigmoid: 100 / (1 + exp(k * (x - x0)))
    score = 100.0 / (1.0 + math.exp(0.8 * (hi_excess - 2.0)))
    return round(score, 1), _status_from_score(score)


def _air_quality_score(co2_ppm: float | None) -> tuple[float, str]:
    """Score air quality using sigmoid decay model (WHO guidelines).

    Uses a logistic function centered at 1000 ppm (WHO cognitive threshold):
    score = 100 / (1 + exp(k * (co2 - threshold)))

    This gives:
    - ~100 at 400 ppm (outdoor ambient)
    - ~95 at 600 ppm
    - ~73 at 900 ppm
    - ~50 at 1000 ppm (inflection point)
    - ~27 at 1100 ppm
    - ~5 at 1400 ppm
    """
    if co2_ppm is None:
        return 50.0, "unknown"

    # Logistic decay: k controls steepness, threshold is inflection point
    k = 0.008  # steepness
    threshold = 1000.0  # WHO cognitive impact threshold
    score = 100.0 / (1.0 + math.exp(k * (co2_ppm - threshold)))
    score = max(0.0, min(100.0, score))
    return round(score, 1), _status_from_score(score)


def _circadian_target_lux(hour: int, minute: int = 0) -> float:
    """Calculate target lux using a circadian rhythm sine-wave model.

    Models the natural human alertness cycle with a smooth curve
    instead of discrete hour buckets.

    Peak alertness (500 lux target) at ~10:00-14:00
    Minimum (20 lux) at ~02:00
    Morning ramp-up and evening wind-down follow sine shape.
    """
    # Convert to fractional hour
    t = hour + minute / 60.0

    # Sine model: peak at 12:00, trough at 00:00
    # Phase-shifted sine: sin(pi * (t - 6) / 12) peaks at t=12
    # Clamp to [0, 1] for the "active" half of the day
    if 5.0 <= t <= 23.0:
        # Active period: smooth sine curve
        phase = math.pi * (t - 5.0) / 18.0  # 0 to pi over 5:00-23:00
        amplitude = math.sin(phase)
    else:
        amplitude = 0.0

    # Map amplitude [0, 1] to lux range [20, 500]
    min_lux = 20.0
    max_lux = 500.0
    return min_lux + amplitude * (max_lux - min_lux)


def _light_score(lux: float | None, hour: int) -> tuple[float, str]:
    """Score light level using circadian-aware Gaussian model.

    Target lux follows a smooth circadian sine-wave curve.
    Scoring uses a log-ratio Gaussian to handle the wide lux range
    (20-500) without bias towards high-lux hours.
    """
    if lux is None:
        return 50.0, "unknown"

    target = _circadian_target_lux(hour)

    # Use log-ratio for scale-invariant scoring
    # This treats "half the target" and "double the target" as equally bad
    if lux <= 0:
        lux = 0.1  # avoid log(0)
    log_ratio = math.log(lux / target)

    # Gaussian in log-space: sigma=0.5 means ~60% tolerance band
    sigma = 0.5
    score = 100.0 * math.exp(-0.5 * (log_ratio / sigma) ** 2)
    return round(max(0.0, min(100.0, score)), 1), _status_from_score(score)


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

    Uses scientifically grounded scoring models:
    - Gaussian bell curves for smooth, continuous scoring
    - Steadman heat index for temperature-humidity interaction
    - Sigmoid decay for CO2 (WHO guidelines)
    - Circadian sine-wave model for light targets

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
    thermal_score, thermal_status = _heat_index_penalty(temperature_c, humidity_pct)
    aq_score, aq_status = _air_quality_score(co2_ppm)
    light_sc, light_status = _light_score(light_lux, hour)

    readings = [
        ComfortReading("temperature", temperature_c, temp_score, WEIGHT_TEMPERATURE, temp_status),
        ComfortReading("humidity", humidity_pct, hum_score, WEIGHT_HUMIDITY, hum_status),
        ComfortReading("thermal_interaction", None, thermal_score, WEIGHT_THERMAL_INTERACTION, thermal_status),
        ComfortReading("air_quality", co2_ppm, aq_score, WEIGHT_AIR_QUALITY, aq_status),
        ComfortReading("light", light_lux, light_sc, WEIGHT_LIGHT, light_status),
    ]

    # Weighted average (weights guaranteed to sum to 1.0)
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
            elif r.factor == "thermal_interaction":
                suggestions.append(
                    "Schwuele Luft — lueften oder Klimaanlage und Entfeuchter einschalten"
                )
            elif r.factor == "air_quality":
                suggestions.append("Fenster oeffnen — CO2-Wert zu hoch")
            elif r.factor == "light":
                target = _circadian_target_lux(hour)
                if lux is not None and lux < target * 0.5:
                    suggestions.append("Beleuchtung erhoehen — zu dunkel fuer die Tageszeit")
                elif lux is not None and lux > target * 2.0:
                    suggestions.append("Beleuchtung dimmen — zu hell fuer die Tageszeit")
        elif r.status == "fair":
            if r.factor == "air_quality" and co2 is not None and co2 > 900:
                suggestions.append("Bald lueften — CO2-Wert steigt")
            elif r.factor == "thermal_interaction":
                suggestions.append(
                    "Leicht schwuel — Luftzirkulation verbessern"
                )

    return suggestions


def _circadian_color_temp(hour: int, minute: int = 0) -> tuple[int, str]:
    """Calculate color temperature using circadian rhythm model.

    Cool/blue light (5000K) during peak alertness hours,
    warm/amber light (2200K) during evening wind-down.
    Smooth transition using cosine interpolation.

    Returns (color_temp_kelvin, reason_text).
    """
    t = hour + minute / 60.0

    # Cosine interpolation between warm and cool
    # Peak cool (5000K) at noon, peak warm (2200K) at midnight
    min_k = 2200
    max_k = 5000

    if 5.0 <= t <= 23.0:
        # Active period: cosine curve
        phase = math.pi * (t - 5.0) / 18.0
        # cos goes from 1 (5am) to -1 (14pm) to 1 (23pm)
        # We want: warm at 5am, cool at ~11am, warm at 23pm
        factor = (1.0 - math.cos(phase)) / 2.0  # 0 at edges, 1 at center
        # But we want peak cool around 10-14, not just center
        # Use sin for that: peaks at middle of range
        factor = math.sin(phase)
        factor = max(0.0, factor)
    else:
        factor = 0.0

    color_temp = int(min_k + factor * (max_k - min_k))

    # Generate reason
    if color_temp >= 4500:
        reason = "Produktivphase — kuehlweisses Arbeitslicht"
    elif color_temp >= 3500:
        reason = "Tageslicht-Ergaenzung — neutralweiss"
    elif color_temp >= 2800:
        reason = "Abendstimmung — warmes Licht"
    else:
        reason = "Nacht/Ruhe — minimales Warmweiss"

    return color_temp, reason


def get_lighting_suggestion(
    current_lux: float | None = None,
    hour: int | None = None,
    cloud_cover_pct: float = 50.0,
    area: str = "Wohnzimmer",
) -> LightingSuggestion:
    """Generate adaptive lighting suggestion using circadian model.

    Target lux and color temperature both follow smooth circadian
    curves instead of discrete hour buckets. Cloud cover modulates
    the target during daytime hours.

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

    # Circadian target lux (smooth sine-wave)
    target_lux = _circadian_target_lux(hour)

    # Circadian color temperature (smooth cosine curve)
    color_temp, reason = _circadian_color_temp(hour)

    # Adjust for cloud cover during daytime (more artificial light needed)
    if 7 <= hour <= 19:
        # sigmoid cloud factor: gentle at low cloud, stronger at high cloud
        cloud_factor = 1.0 + 0.5 / (1.0 + math.exp(-0.06 * (cloud_cover_pct - 50)))
        target_lux *= cloud_factor

    # Calculate brightness percentage (0-100)
    if current_lux is not None and current_lux >= target_lux:
        brightness = 0
        reason = "Genuegend Tageslicht — keine Beleuchtung noetig"
    else:
        deficit = target_lux - (current_lux or 0)
        # Square root scaling: gentler brightness increase for small deficits
        ratio = deficit / max(1.0, target_lux)
        brightness = min(100, max(5, int(math.sqrt(ratio) * 100)))

    return LightingSuggestion(
        area=area,
        current_lux=current_lux,
        target_lux=round(target_lux, 0),
        brightness_percent=brightness,
        color_temp_kelvin=color_temp,
        reason=reason,
    )
