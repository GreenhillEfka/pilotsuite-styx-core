"""Helligkeits- und Lautstaerke-Kurven fuer den Lichtwecker.

5 Kurventypen basierend auf psychophysikalischer Forschung:
- linear:       Gleichmaessiger Anstieg (Referenz)
- quadratic:    Weber-Fechner (t^2) — perceptuell linear
- sigmoid:      S-Kurve (logistisch, k=8) — sanfter Start/Ende
- philips_hue:  3-Phasen Philips-Referenz — warmrot bis Tageslicht
- exponential:  Exponentielle Kurve (base=10) — langsamer Start

Alle Funktionen:
  Input:  t ∈ [0.0, 1.0] (Fortschritt)
  Output: y ∈ [0.0, 1.0] (normalisierter Wert)
"""

import math
from typing import Callable, Dict, List

from copilot_core.modules.sunrise_alarm.models import CurveType


def linear(t: float) -> float:
    """Linearer Verlauf: y = t."""
    return max(0.0, min(1.0, t))


def quadratic(t: float) -> float:
    """Weber-Fechner Kurve: y = t^2.

    Menschliche Helligkeitswahrnehmung folgt einem logarithmischen Gesetz.
    Quadratischer Anstieg der physikalischen Helligkeit ergibt
    perceptuell linearen Anstieg.
    """
    t = max(0.0, min(1.0, t))
    return t * t


def sigmoid(t: float, k: float = 8.0) -> float:
    """Logistische S-Kurve: y = 1 / (1 + exp(-k*(t-0.5))).

    Sanfter Start und sanftes Ende — ideal fuer natuerliches Aufwachen.
    k bestimmt die Steilheit (Standard k=8 ergibt 90% in mittleren 50%).
    """
    t = max(0.0, min(1.0, t))
    raw = 1.0 / (1.0 + math.exp(-k * (t - 0.5)))
    # Normalisieren auf exakt [0, 1]
    y_min = 1.0 / (1.0 + math.exp(-k * (0.0 - 0.5)))
    y_max = 1.0 / (1.0 + math.exp(-k * (1.0 - 0.5)))
    return (raw - y_min) / (y_max - y_min) if y_max != y_min else t


def philips_hue(t: float) -> float:
    """Philips Hue 3-Phasen Sunrise-Kurve.

    Phase 1 (0-30%):   Tiefrot, sehr langsam (0→5%)
    Phase 2 (30-70%):  Warm, moderater Anstieg (5→50%)
    Phase 3 (70-100%): Tageslicht, schneller Anstieg (50→100%)

    Basiert auf der Philips Hue Wake-up Light Referenz-Implementierung.
    """
    t = max(0.0, min(1.0, t))
    if t <= 0.3:
        # Phase 1: Tiefrot → Warmrot (sehr langsam)
        p = t / 0.3
        return 0.05 * (p * p)
    elif t <= 0.7:
        # Phase 2: Warmrot → Warmweiss (moderat)
        p = (t - 0.3) / 0.4
        return 0.05 + 0.45 * p
    else:
        # Phase 3: Warmweiss → Tageslicht (schnell)
        p = (t - 0.7) / 0.3
        return 0.50 + 0.50 * (p * p * (3.0 - 2.0 * p))  # smoothstep


def exponential(t: float, base: float = 10.0) -> float:
    """Exponentielle Kurve: y = (base^t - 1) / (base - 1).

    Sehr langsamer Start, dann rapider Anstieg.
    Ideal wenn man moeglichst lange sanft geweckt werden moechte.
    """
    t = max(0.0, min(1.0, t))
    if base <= 1.0:
        return t
    return (base ** t - 1.0) / (base - 1.0)


# -- Registry + Hilfsfunktionen --

_CURVE_FUNCTIONS: Dict[str, Callable[[float], float]] = {
    CurveType.LINEAR.value: linear,
    CurveType.QUADRATIC.value: quadratic,
    CurveType.SIGMOID.value: sigmoid,
    CurveType.PHILIPS_HUE.value: philips_hue,
    CurveType.EXPONENTIAL.value: exponential,
}

CURVE_DESCRIPTIONS: Dict[str, str] = {
    CurveType.LINEAR.value: "Gleichmaessiger Anstieg (Referenz)",
    CurveType.QUADRATIC.value: "Weber-Fechner — perceptuell linear (empfohlen)",
    CurveType.SIGMOID.value: "S-Kurve — sanfter Start und Ende",
    CurveType.PHILIPS_HUE.value: "Philips 3-Phasen — warmrot bis Tageslicht",
    CurveType.EXPONENTIAL.value: "Exponentiell — sehr langsamer Start",
}


def get_curve(curve_type: str) -> Callable[[float], float]:
    """Gibt die Kurvenfunktion fuer einen Typ zurueck."""
    return _CURVE_FUNCTIONS.get(curve_type, quadratic)


def reverse(curve_fn: Callable[[float], float]) -> Callable[[float], float]:
    """Kehrt eine Kurve um (fuer Sunset/Einschlafen): y = 1 - f(1-t)."""
    def reversed_curve(t: float) -> float:
        return 1.0 - curve_fn(1.0 - t)
    return reversed_curve


def interpolate_value(start: float, end: float, t: float,
                      curve_fn: Callable[[float], float]) -> float:
    """Interpoliert einen Wert von start nach end mit der gegebenen Kurve."""
    y = curve_fn(t)
    return start + (end - start) * y


def interpolate_cct(cct_start: int, cct_end: int, t: float,
                    curve_fn: Callable[[float], float]) -> int:
    """Interpoliert die Farbtemperatur von start nach end."""
    y = curve_fn(t)
    return int(cct_start + (cct_end - cct_start) * y)


def philips_hue_phase_cct(t: float, cct_start: int = 1800,
                          cct_end: int = 5000) -> int:
    """Farbtemperatur-Verlauf passend zur Philips-3-Phasen-Kurve.

    Phase 1 (0-30%):   1800K (Tiefrot)
    Phase 2 (30-70%):  1800K → 3000K (Warmweiss)
    Phase 3 (70-100%): 3000K → cct_end (Tageslicht)
    """
    t = max(0.0, min(1.0, t))
    if t <= 0.3:
        return cct_start
    elif t <= 0.7:
        p = (t - 0.3) / 0.4
        return int(cct_start + (3000 - cct_start) * p)
    else:
        p = (t - 0.7) / 0.3
        return int(3000 + (cct_end - 3000) * p)


def get_all_curves() -> List[dict]:
    """Gibt alle verfuegbaren Kurventypen mit Beschreibung und Samples zurueck."""
    result = []
    for curve_type in CurveType:
        fn = _CURVE_FUNCTIONS[curve_type.value]
        # 11 Samples (0%, 10%, ..., 100%)
        samples = [round(fn(i / 10.0), 3) for i in range(11)]
        result.append({
            "type": curve_type.value,
            "description": CURVE_DESCRIPTIONS.get(curve_type.value, ""),
            "samples": samples,
        })
    return result
