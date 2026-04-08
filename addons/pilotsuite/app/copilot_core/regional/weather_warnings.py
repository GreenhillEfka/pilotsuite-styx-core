"""DWD/ZAMG/MeteoSchweiz Weather Warnings Manager (v5.16.0).

Fetches and parses official weather warnings from national
meteorological services. Primary focus on DWD (Germany) with
support for ZAMG (Austria) and MeteoSchweiz (Switzerland).

Design: Zero-config — uses RegionalContextProvider to auto-detect
the correct warning service based on user's location.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import IntEnum
from typing import Optional

logger = logging.getLogger(__name__)


# ── Warning severity levels ──────────────────────────────────────────────

class WarningSeverity(IntEnum):
    """Warning severity levels (aligned with DWD/CAP standard)."""

    MINOR = 1       # Wetterwarnung (yellow)
    MODERATE = 2    # Markante Wetterwarnung (orange)
    SEVERE = 3      # Unwetterwarnung (red)
    EXTREME = 4     # Extreme Unwetterwarnung (violet/purple)


class WarningType(IntEnum):
    """Weather warning event types."""

    THUNDERSTORM = 1    # Gewitter
    WIND = 2            # Wind/Sturm
    RAIN = 3            # Starkregen/Dauerregen
    SNOW = 4            # Schneefall
    ICE = 5             # Glaette/Glatteis
    FOG = 6             # Nebel
    FROST = 7           # Frost
    HEAT = 8            # Hitze
    UV = 9              # UV-Strahlung
    FLOOD = 10          # Hochwasser
    OTHER = 99


# ── DWD event type mapping ───────────────────────────────────────────────

_DWD_EVENT_MAP: dict[str, WarningType] = {
    "GEWITTER": WarningType.THUNDERSTORM,
    "STARKES GEWITTER": WarningType.THUNDERSTORM,
    "SCHWERES GEWITTER": WarningType.THUNDERSTORM,
    "EXTREMES GEWITTER": WarningType.THUNDERSTORM,
    "WIND": WarningType.WIND,
    "STURMBÖEN": WarningType.WIND,
    "STURM": WarningType.WIND,
    "SCHWERE STURMBÖEN": WarningType.WIND,
    "ORKANBÖEN": WarningType.WIND,
    "STARKREGEN": WarningType.RAIN,
    "DAUERREGEN": WarningType.RAIN,
    "ERGIEBIGER DAUERREGEN": WarningType.RAIN,
    "EXTREM ERGIEBIGER DAUERREGEN": WarningType.RAIN,
    "SCHNEEFALL": WarningType.SNOW,
    "STARKER SCHNEEFALL": WarningType.SNOW,
    "EXTREM STARKER SCHNEEFALL": WarningType.SNOW,
    "SCHNEEVERWEHUNG": WarningType.SNOW,
    "GLATTEIS": WarningType.ICE,
    "GLÄTTE": WarningType.ICE,
    "NEBEL": WarningType.FOG,
    "FROST": WarningType.FROST,
    "STRENGER FROST": WarningType.FROST,
    "HITZE": WarningType.HEAT,
    "EXTREME HITZE": WarningType.HEAT,
    "UV-INDEX": WarningType.UV,
    "HOCHWASSER": WarningType.FLOOD,
}

# DWD level mapping
_DWD_LEVEL_MAP: dict[int, WarningSeverity] = {
    1: WarningSeverity.MINOR,
    2: WarningSeverity.MODERATE,
    3: WarningSeverity.SEVERE,
    4: WarningSeverity.EXTREME,
}


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class WeatherWarning:
    """A single weather warning."""

    id: str
    severity: int  # WarningSeverity value
    severity_label: str  # "Wetterwarnung", "Unwetterwarnung", etc.
    warning_type: int  # WarningType value
    warning_type_label: str  # "Gewitter", "Wind", etc.
    headline: str
    description: str
    instruction: str
    region: str
    start: str  # ISO timestamp
    end: str  # ISO timestamp
    source: str  # "dwd", "zamg", "meteoschweiz"
    is_active: bool
    color: str  # hex color for UI


@dataclass
class WarningImpact:
    """PV/energy impact assessment for a warning."""

    warning_id: str
    pv_impact: str  # "none", "low", "moderate", "high", "severe"
    pv_reduction_pct: int  # estimated PV reduction 0-100
    grid_risk: str  # "none", "low", "moderate", "high"
    recommendation_de: str
    recommendation_en: str


@dataclass
class WarningsOverview:
    """Overview of all active warnings."""

    total: int
    by_severity: dict[str, int]
    highest_severity: int
    highest_severity_label: str
    has_pv_impact: bool
    has_grid_risk: bool
    warnings: list[dict]
    impacts: list[dict]
    last_updated: str
    source: str


# ── Severity labels and colors ───────────────────────────────────────────

_SEVERITY_LABELS_DE: dict[int, str] = {
    1: "Wetterwarnung",
    2: "Markante Wetterwarnung",
    3: "Unwetterwarnung",
    4: "Extreme Unwetterwarnung",
}

_SEVERITY_COLORS: dict[int, str] = {
    1: "#FFFF00",   # Yellow
    2: "#FF8C00",   # Orange
    3: "#FF0000",   # Red
    4: "#800080",   # Violet/Purple
}

_WARNING_TYPE_LABELS_DE: dict[int, str] = {
    1: "Gewitter",
    2: "Wind/Sturm",
    3: "Starkregen/Dauerregen",
    4: "Schneefall",
    5: "Glätte/Glatteis",
    6: "Nebel",
    7: "Frost",
    8: "Hitze",
    9: "UV-Strahlung",
    10: "Hochwasser",
    99: "Sonstiges",
}


# ── Impact assessment rules ──────────────────────────────────────────────

_PV_IMPACT_RULES: dict[int, tuple[str, int]] = {
    # warning_type -> (impact_level, reduction_pct)
    WarningType.THUNDERSTORM: ("high", 80),
    WarningType.WIND: ("moderate", 10),
    WarningType.RAIN: ("moderate", 60),
    WarningType.SNOW: ("high", 90),
    WarningType.ICE: ("low", 20),
    WarningType.FOG: ("moderate", 50),
    WarningType.FROST: ("low", 5),
    WarningType.HEAT: ("low", 10),  # heat actually reduces efficiency slightly
    WarningType.UV: ("none", 0),
    WarningType.FLOOD: ("none", 0),
    WarningType.OTHER: ("none", 0),
}

_GRID_RISK_RULES: dict[int, str] = {
    WarningType.THUNDERSTORM: "high",
    WarningType.WIND: "high",
    WarningType.RAIN: "low",
    WarningType.SNOW: "moderate",
    WarningType.ICE: "moderate",
    WarningType.FOG: "none",
    WarningType.FROST: "low",
    WarningType.HEAT: "moderate",
    WarningType.UV: "none",
    WarningType.FLOOD: "high",
    WarningType.OTHER: "none",
}


# ── Recommendations ──────────────────────────────────────────────────────

_RECOMMENDATIONS_DE: dict[int, str] = {
    WarningType.THUNDERSTORM: "Batterie laden, Einspeisung stoppen. Geräte vom Netz nehmen.",
    WarningType.WIND: "PV-Anlage prüfen. Bei Orkan ggf. Wechselrichter abschalten.",
    WarningType.RAIN: "Reduzierte PV-Leistung einplanen. Günstige Netzstromzeiten nutzen.",
    WarningType.SNOW: "PV-Ertrag stark reduziert. Schneelast auf Modulen beobachten.",
    WarningType.ICE: "Vorsicht bei Außenarbeiten. Wärmepumpe auf Frostschutz prüfen.",
    WarningType.FOG: "PV-Ertrag morgens reduziert. Verbrauch auf Nachmittag verschieben.",
    WarningType.FROST: "Wärmepumpe auf Frostschutz. Heizungsverbrauch steigt.",
    WarningType.HEAT: "Klimaanlage effizient nutzen. PV-Effizienz leicht reduziert.",
    WarningType.UV: "Keine Auswirkung auf Energiesystem.",
    WarningType.FLOOD: "Keller-/Außengeräte sichern. Netzausfall möglich.",
    WarningType.OTHER: "Aktuelle Wetterlage beobachten.",
}

_RECOMMENDATIONS_EN: dict[int, str] = {
    WarningType.THUNDERSTORM: "Charge battery, stop feed-in. Disconnect sensitive devices.",
    WarningType.WIND: "Check PV system. Consider shutting off inverter during hurricane.",
    WarningType.RAIN: "Plan for reduced PV output. Use cheap grid power windows.",
    WarningType.SNOW: "PV output severely reduced. Monitor snow load on panels.",
    WarningType.ICE: "Caution with outdoor work. Check heat pump frost protection.",
    WarningType.FOG: "PV output reduced mornings. Shift consumption to afternoon.",
    WarningType.FROST: "Heat pump frost protection. Heating consumption increases.",
    WarningType.HEAT: "Use AC efficiently. PV efficiency slightly reduced.",
    WarningType.UV: "No impact on energy system.",
    WarningType.FLOOD: "Secure basement/outdoor equipment. Grid outage possible.",
    WarningType.OTHER: "Monitor current weather situation.",
}


# ── Main Warning Manager ─────────────────────────────────────────────────

class WeatherWarningManager:
    """Manages weather warnings from DWD/ZAMG/MeteoSchweiz.

    Parses warnings, assesses PV/energy impact, and provides
    actionable recommendations in German and English.
    """

    def __init__(self, country: str = "DE", region: str = ""):
        self._country = country
        self._region = region
        self._warnings: list[WeatherWarning] = []
        self._last_updated: float = 0
        self._cache_ttl: float = 300  # 5 minutes
        self._warning_counter: int = 0

    @property
    def source(self) -> str:
        """Warning service source name."""
        sources = {"DE": "dwd", "AT": "zamg", "CH": "meteoschweiz"}
        return sources.get(self._country, "dwd")

    def update_region(self, country: str, region: str) -> None:
        """Update country and region for filtering."""
        self._country = country
        self._region = region

    def process_dwd_warnings(self, raw_data: dict) -> list[WeatherWarning]:
        """Parse DWD warning JSON into structured warnings.

        DWD format: {"time": ..., "warnings": {"cell_id": [warning, ...]}}
        or newer: {"warnings": [warning, ...]}
        """
        warnings: list[WeatherWarning] = []
        now = datetime.now()

        # Handle both old (dict of lists) and new (list) formats
        raw_warnings = []
        w_data = raw_data.get("warnings", {})
        if isinstance(w_data, dict):
            for _cell_id, cell_warnings in w_data.items():
                if isinstance(cell_warnings, list):
                    raw_warnings.extend(cell_warnings)
        elif isinstance(w_data, list):
            raw_warnings = w_data

        for w in raw_warnings:
            try:
                # Extract event name and map to type
                event = (w.get("event", "") or "").upper().strip()
                warning_type = WarningType.OTHER
                for key, wtype in _DWD_EVENT_MAP.items():
                    if key in event:
                        warning_type = wtype
                        break

                # Severity level
                level = w.get("level", 1)
                severity = _DWD_LEVEL_MAP.get(level, WarningSeverity.MINOR)

                # Time parsing (DWD uses milliseconds)
                start_ms = w.get("start", 0)
                end_ms = w.get("end", 0)
                start_dt = datetime.fromtimestamp(start_ms / 1000) if start_ms else now
                end_dt = datetime.fromtimestamp(end_ms / 1000) if end_ms else now

                # Active check
                is_active = start_dt <= now <= end_dt if end_ms else start_dt <= now

                # Region name from DWD
                region_name = w.get("regionName", "")
                if isinstance(region_name, list):
                    region_name = ", ".join(region_name)

                self._warning_counter += 1
                warning = WeatherWarning(
                    id=f"dwd-{self._warning_counter}",
                    severity=int(severity),
                    severity_label=_SEVERITY_LABELS_DE.get(int(severity), "Unbekannt"),
                    warning_type=int(warning_type),
                    warning_type_label=_WARNING_TYPE_LABELS_DE.get(
                        int(warning_type), "Sonstiges"
                    ),
                    headline=w.get("headline", w.get("event", "Wetterwarnung")),
                    description=w.get("description", ""),
                    instruction=w.get("instruction", "") or "",
                    region=region_name,
                    start=start_dt.isoformat(),
                    end=end_dt.isoformat(),
                    source="dwd",
                    is_active=is_active,
                    color=_SEVERITY_COLORS.get(int(severity), "#FFFF00"),
                )
                warnings.append(warning)
            except Exception as exc:
                logger.debug("Failed to parse DWD warning: %s", exc)

        self._warnings = warnings
        self._last_updated = time.time()
        return warnings

    def process_generic_warnings(
        self, warnings_list: list[dict], source: str = "generic"
    ) -> list[WeatherWarning]:
        """Process generic warning format (for ZAMG, MeteoSchweiz, or manual input).

        Each dict: {severity, type, headline, description, instruction,
                    region, start, end}
        """
        warnings: list[WeatherWarning] = []
        now = datetime.now()

        for w in warnings_list:
            try:
                severity = min(max(int(w.get("severity", 1)), 1), 4)
                warning_type = int(w.get("type", WarningType.OTHER))

                start_str = w.get("start", now.isoformat())
                end_str = w.get("end", now.isoformat())

                # Parse ISO timestamps
                try:
                    start_dt = datetime.fromisoformat(start_str)
                except (ValueError, TypeError):
                    start_dt = now
                try:
                    end_dt = datetime.fromisoformat(end_str)
                except (ValueError, TypeError):
                    end_dt = now

                is_active = start_dt <= now <= end_dt

                self._warning_counter += 1
                warning = WeatherWarning(
                    id=f"{source}-{self._warning_counter}",
                    severity=severity,
                    severity_label=_SEVERITY_LABELS_DE.get(severity, "Unbekannt"),
                    warning_type=warning_type,
                    warning_type_label=_WARNING_TYPE_LABELS_DE.get(
                        warning_type, "Sonstiges"
                    ),
                    headline=w.get("headline", "Wetterwarnung"),
                    description=w.get("description", ""),
                    instruction=w.get("instruction", ""),
                    region=w.get("region", self._region),
                    start=start_dt.isoformat(),
                    end=end_dt.isoformat(),
                    source=source,
                    is_active=is_active,
                    color=_SEVERITY_COLORS.get(severity, "#FFFF00"),
                )
                warnings.append(warning)
            except Exception as exc:
                logger.debug("Failed to parse %s warning: %s", source, exc)

        self._warnings = warnings
        self._last_updated = time.time()
        return warnings

    def assess_impact(self, warning: WeatherWarning) -> WarningImpact:
        """Assess PV/energy impact of a warning."""
        wtype = warning.warning_type
        pv_impact, pv_reduction = _PV_IMPACT_RULES.get(wtype, ("none", 0))
        grid_risk = _GRID_RISK_RULES.get(wtype, "none")

        # Scale by severity
        severity_multiplier = {1: 0.5, 2: 0.75, 3: 1.0, 4: 1.0}
        pv_reduction = int(pv_reduction * severity_multiplier.get(warning.severity, 1.0))

        # Upgrade impact if severity is extreme
        if warning.severity >= WarningSeverity.SEVERE:
            if pv_impact == "low":
                pv_impact = "moderate"
            elif pv_impact == "moderate":
                pv_impact = "high"
            if grid_risk == "low":
                grid_risk = "moderate"
            elif grid_risk == "moderate":
                grid_risk = "high"

        return WarningImpact(
            warning_id=warning.id,
            pv_impact=pv_impact,
            pv_reduction_pct=min(pv_reduction, 100),
            grid_risk=grid_risk,
            recommendation_de=_RECOMMENDATIONS_DE.get(wtype, "Wetterlage beobachten."),
            recommendation_en=_RECOMMENDATIONS_EN.get(wtype, "Monitor weather."),
        )

    def get_active_warnings(self) -> list[WeatherWarning]:
        """Get only currently active warnings."""
        return [w for w in self._warnings if w.is_active]

    def get_warnings_by_severity(
        self, min_severity: int = WarningSeverity.MINOR
    ) -> list[WeatherWarning]:
        """Get warnings at or above a severity level."""
        return [w for w in self._warnings if w.severity >= min_severity]

    def get_overview(self) -> WarningsOverview:
        """Get full warnings overview with impacts."""
        active = self.get_active_warnings()

        by_severity = {
            "minor": sum(1 for w in active if w.severity == 1),
            "moderate": sum(1 for w in active if w.severity == 2),
            "severe": sum(1 for w in active if w.severity == 3),
            "extreme": sum(1 for w in active if w.severity == 4),
        }

        highest = max((w.severity for w in active), default=0)

        # Assess impacts
        impacts = []
        has_pv = False
        has_grid = False
        for w in active:
            impact = self.assess_impact(w)
            impacts.append(asdict(impact))
            if impact.pv_impact not in ("none",):
                has_pv = True
            if impact.grid_risk not in ("none",):
                has_grid = True

        return WarningsOverview(
            total=len(active),
            by_severity=by_severity,
            highest_severity=highest,
            highest_severity_label=_SEVERITY_LABELS_DE.get(highest, "Keine Warnung"),
            has_pv_impact=has_pv,
            has_grid_risk=has_grid,
            warnings=[asdict(w) for w in active],
            impacts=impacts,
            last_updated=datetime.fromtimestamp(self._last_updated).isoformat()
            if self._last_updated
            else "",
            source=self.source,
        )

    def get_pv_warnings(self) -> list[dict]:
        """Get warnings that affect PV production."""
        result = []
        for w in self.get_active_warnings():
            impact = self.assess_impact(w)
            if impact.pv_impact != "none":
                result.append({
                    "warning": asdict(w),
                    "impact": asdict(impact),
                })
        return result

    def get_grid_warnings(self) -> list[dict]:
        """Get warnings that affect grid stability."""
        result = []
        for w in self.get_active_warnings():
            impact = self.assess_impact(w)
            if impact.grid_risk != "none":
                result.append({
                    "warning": asdict(w),
                    "impact": asdict(impact),
                })
        return result

    def get_summary_text(self, language: str = "de") -> str:
        """Get human-readable warning summary."""
        active = self.get_active_warnings()
        if not active:
            if language == "de":
                return "Keine aktiven Wetterwarnungen."
            return "No active weather warnings."

        highest = max(active, key=lambda w: w.severity)

        if language == "de":
            lines = [
                f"⚠️ {len(active)} aktive Wetterwarnung(en)",
                f"Höchste Stufe: {highest.severity_label}",
            ]
            for w in sorted(active, key=lambda x: -x.severity):
                impact = self.assess_impact(w)
                lines.append(
                    f"  • {w.warning_type_label}: {w.headline} "
                    f"(PV: -{impact.pv_reduction_pct}%)"
                )
            return "\n".join(lines)
        else:
            lines = [
                f"⚠️ {len(active)} active weather warning(s)",
                f"Highest level: {highest.severity_label}",
            ]
            for w in sorted(active, key=lambda x: -x.severity):
                impact = self.assess_impact(w)
                lines.append(
                    f"  • {w.warning_type_label}: {w.headline} "
                    f"(PV: -{impact.pv_reduction_pct}%)"
                )
            return "\n".join(lines)

    @property
    def cache_valid(self) -> bool:
        """Check if cached warnings are still valid."""
        return (time.time() - self._last_updated) < self._cache_ttl

    @property
    def warning_count(self) -> int:
        """Number of active warnings."""
        return len(self.get_active_warnings())
