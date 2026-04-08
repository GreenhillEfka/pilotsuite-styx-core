"""Proactive Alert System — Combined Weather+Price+Grid Alerts (v5.19.0).

Aggregates data from weather warnings, tariff engine, demand response,
and PV forecasts to generate proactive energy recommendations.
Pushes alerts to HA via webhook for notifications.

Zero-config: Uses all regional services automatically.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Optional

logger = logging.getLogger(__name__)


# ── Alert priority ───────────────────────────────────────────────────────

class AlertPriority(IntEnum):
    """Alert priority levels."""

    INFO = 1
    ADVISORY = 2
    WARNING = 3
    CRITICAL = 4


class AlertCategory(str):
    """Alert categories."""

    WEATHER = "weather"
    PRICE = "price"
    GRID = "grid"
    PV = "pv"
    BATTERY = "battery"
    COMBINED = "combined"


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class ProactiveAlert:
    """A proactive energy alert."""

    id: str
    priority: int
    priority_label: str
    category: str
    title_de: str
    title_en: str
    message_de: str
    message_en: str
    action: str  # "charge", "discharge", "shift", "curtail", "protect", "info"
    action_detail: str
    data: dict  # extra context data
    created_at: str
    expires_at: str
    is_active: bool
    icon: str  # mdi icon


@dataclass
class AlertSummary:
    """Summary of all active alerts."""

    total: int
    by_priority: dict[str, int]
    by_category: dict[str, int]
    highest_priority: int
    highest_priority_label: str
    alerts: list[dict]
    last_evaluated: str


# ── Priority labels and icons ────────────────────────────────────────────

_PRIORITY_LABELS = {
    1: "Info",
    2: "Hinweis",
    3: "Warnung",
    4: "Kritisch",
}

_CATEGORY_ICONS = {
    "weather": "mdi:weather-lightning",
    "price": "mdi:currency-eur",
    "grid": "mdi:transmission-tower",
    "pv": "mdi:solar-panel",
    "battery": "mdi:battery-alert",
    "combined": "mdi:alert-circle",
}


# ── Alert rule definitions ───────────────────────────────────────────────

@dataclass
class AlertRule:
    """Definition of an alert rule."""

    id: str
    category: str
    check_fn_name: str  # method name on ProactiveAlertEngine
    cooldown_minutes: int = 30


# ── Main Alert Engine ────────────────────────────────────────────────────

class ProactiveAlertEngine:
    """Generates proactive alerts from regional data sources.

    Monitors:
    - Weather warnings → PV impact, grid risk
    - Electricity prices → price spikes, cheap windows
    - Grid signals → demand response
    - Solar forecast → PV production changes
    """

    def __init__(self):
        self._alerts: list[ProactiveAlert] = []
        self._alert_counter: int = 0
        self._cooldowns: dict[str, float] = {}
        self._last_evaluated: float = 0
        self._max_alerts: int = 50

        # Thresholds (configurable)
        self._price_spike_ct: float = 35.0  # ct/kWh
        self._price_low_ct: float = 20.0    # ct/kWh
        self._pv_drop_pct: float = 50.0     # PV reduction threshold

    def configure(
        self,
        price_spike_ct: float | None = None,
        price_low_ct: float | None = None,
        pv_drop_pct: float | None = None,
    ) -> None:
        """Configure alert thresholds."""
        if price_spike_ct is not None:
            self._price_spike_ct = price_spike_ct
        if price_low_ct is not None:
            self._price_low_ct = price_low_ct
        if pv_drop_pct is not None:
            self._pv_drop_pct = pv_drop_pct

    def _can_fire(self, rule_id: str, cooldown_minutes: int = 30) -> bool:
        """Check if alert can fire (cooldown not active)."""
        last = self._cooldowns.get(rule_id, 0)
        return (time.time() - last) > cooldown_minutes * 60

    def _fire_alert(
        self,
        rule_id: str,
        priority: int,
        category: str,
        title_de: str,
        title_en: str,
        message_de: str,
        message_en: str,
        action: str,
        action_detail: str = "",
        data: dict | None = None,
        ttl_minutes: int = 120,
        cooldown_minutes: int = 30,
    ) -> ProactiveAlert:
        """Create and store an alert."""
        if not self._can_fire(rule_id, cooldown_minutes):
            return None

        self._alert_counter += 1
        now = datetime.now()

        alert = ProactiveAlert(
            id=f"alert-{self._alert_counter}",
            priority=priority,
            priority_label=_PRIORITY_LABELS.get(priority, "Info"),
            category=category,
            title_de=title_de,
            title_en=title_en,
            message_de=message_de,
            message_en=message_en,
            action=action,
            action_detail=action_detail,
            data=data or {},
            created_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=ttl_minutes)).isoformat(),
            is_active=True,
            icon=_CATEGORY_ICONS.get(category, "mdi:alert"),
        )

        self._alerts.append(alert)
        self._cooldowns[rule_id] = time.time()

        # Trim old alerts
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]

        logger.info("Alert fired: [%s] %s", category, title_de)
        return alert

    def evaluate_weather(self, warning_overview: dict) -> list[ProactiveAlert]:
        """Evaluate weather warnings and generate alerts."""
        alerts = []
        total = warning_overview.get("total", 0)
        highest = warning_overview.get("highest_severity", 0)
        has_pv = warning_overview.get("has_pv_impact", False)
        has_grid = warning_overview.get("has_grid_risk", False)
        warnings_list = warning_overview.get("warnings", [])
        impacts = warning_overview.get("impacts", [])

        if total == 0:
            return alerts

        # Severe weather alert
        if highest >= 3:
            headline = ""
            for w in warnings_list:
                if w.get("severity", 0) >= 3:
                    headline = w.get("headline", "Unwetter")
                    break

            alert = self._fire_alert(
                rule_id="weather_severe",
                priority=AlertPriority.CRITICAL,
                category="weather",
                title_de="Unwetterwarnung aktiv",
                title_en="Severe weather warning active",
                message_de=f"{headline}. Batterie laden und Einspeisung prüfen.",
                message_en=f"{headline}. Charge battery, check feed-in.",
                action="protect",
                action_detail="charge_battery,stop_feedin",
                data={"severity": highest, "warning_count": total},
                cooldown_minutes=60,
            )
            if alert:
                alerts.append(alert)

        # PV impact alert
        if has_pv:
            max_reduction = 0
            for imp in impacts:
                red = imp.get("pv_reduction_pct", 0)
                if red > max_reduction:
                    max_reduction = red

            if max_reduction >= self._pv_drop_pct:
                alert = self._fire_alert(
                    rule_id="weather_pv_impact",
                    priority=AlertPriority.WARNING,
                    category="pv",
                    title_de=f"PV-Ertrag stark reduziert (-{max_reduction}%)",
                    title_en=f"PV output severely reduced (-{max_reduction}%)",
                    message_de="Wetterbedingt stark reduzierter PV-Ertrag. Netzstrom einplanen.",
                    message_en="Weather-related PV output drop. Plan for grid power.",
                    action="shift",
                    action_detail="use_grid_power,shift_loads",
                    data={"pv_reduction_pct": max_reduction},
                    cooldown_minutes=60,
                )
                if alert:
                    alerts.append(alert)

        # Grid risk alert
        if has_grid and highest >= 3:
            alert = self._fire_alert(
                rule_id="weather_grid_risk",
                priority=AlertPriority.WARNING,
                category="grid",
                title_de="Netzstörungsrisiko durch Unwetter",
                title_en="Grid disruption risk from severe weather",
                message_de="Batterie laden. Verbrauch reduzieren. Netzausfall möglich.",
                message_en="Charge battery. Reduce consumption. Grid outage possible.",
                action="protect",
                action_detail="charge_battery,reduce_consumption",
                data={"grid_risk": True},
                cooldown_minutes=120,
            )
            if alert:
                alerts.append(alert)

        return alerts

    def evaluate_prices(self, tariff_summary: dict) -> list[ProactiveAlert]:
        """Evaluate electricity prices and generate alerts."""
        alerts = []
        current_ct = tariff_summary.get("current_price_ct_kwh", 0)
        current_level = tariff_summary.get("current_level", "normal")
        min_ct = (tariff_summary.get("min_price_eur_kwh", 0) or 0) * 100
        max_ct = (tariff_summary.get("max_price_eur_kwh", 0) or 0) * 100
        min_hour = tariff_summary.get("min_hour", "")

        # Price spike alert
        if current_ct >= self._price_spike_ct or current_level in ("high", "very_high"):
            alert = self._fire_alert(
                rule_id="price_spike",
                priority=AlertPriority.ADVISORY,
                category="price",
                title_de=f"Strompreis hoch: {current_ct:.1f} ct/kWh",
                title_en=f"Electricity price high: {current_ct:.1f} ct/kWh",
                message_de=f"Verbrauch verschieben! Günstigster Zeitpunkt: {min_hour} ({min_ct:.1f} ct/kWh).",
                message_en=f"Shift consumption! Cheapest: {min_hour} ({min_ct:.1f} ct/kWh).",
                action="shift",
                action_detail=f"shift_to_{min_hour}",
                data={
                    "current_ct": current_ct,
                    "min_ct": min_ct,
                    "min_hour": min_hour,
                },
                cooldown_minutes=30,
            )
            if alert:
                alerts.append(alert)

        # Cheap price window alert
        if current_ct <= self._price_low_ct or current_level in ("very_low", "low"):
            alert = self._fire_alert(
                rule_id="price_low",
                priority=AlertPriority.INFO,
                category="price",
                title_de=f"Strompreis niedrig: {current_ct:.1f} ct/kWh",
                title_en=f"Electricity price low: {current_ct:.1f} ct/kWh",
                message_de="Jetzt laden und energieintensive Geräte nutzen!",
                message_en="Charge now and use energy-intensive appliances!",
                action="charge",
                action_detail="charge_battery,run_appliances",
                data={"current_ct": current_ct},
                cooldown_minutes=60,
            )
            if alert:
                alerts.append(alert)

        # Large price spread (arbitrage opportunity)
        spread = max_ct - min_ct
        if spread >= 15.0:
            alert = self._fire_alert(
                rule_id="price_arbitrage",
                priority=AlertPriority.INFO,
                category="price",
                title_de=f"Preisspreizung: {spread:.1f} ct/kWh Unterschied",
                title_en=f"Price spread: {spread:.1f} ct/kWh difference",
                message_de=f"Batterie um {min_hour} laden, bei Spitzenpreis entladen.",
                message_en=f"Charge battery at {min_hour}, discharge at peak.",
                action="shift",
                action_detail="battery_arbitrage",
                data={"spread_ct": spread, "min_hour": min_hour},
                cooldown_minutes=120,
            )
            if alert:
                alerts.append(alert)

        return alerts

    def evaluate_pv(self, pv_factor: float, solar_data: dict) -> list[ProactiveAlert]:
        """Evaluate PV production and generate alerts."""
        alerts = []
        is_daylight = solar_data.get("is_daylight", False)
        elevation = solar_data.get("elevation_deg", 0)

        # High PV production — encourage self-consumption
        if is_daylight and pv_factor >= 0.7:
            alert = self._fire_alert(
                rule_id="pv_high",
                priority=AlertPriority.INFO,
                category="pv",
                title_de="Hohe PV-Produktion erwartet",
                title_en="High PV production expected",
                message_de="Waschmaschine, Spülmaschine etc. jetzt starten für maximale Eigennutzung.",
                message_en="Start washing machine, dishwasher etc. now for maximum self-consumption.",
                action="shift",
                action_detail="run_appliances_now",
                data={"pv_factor": pv_factor, "elevation_deg": elevation},
                cooldown_minutes=120,
            )
            if alert:
                alerts.append(alert)

        # Sunset approaching — charge battery from PV
        if is_daylight and 0.1 <= pv_factor <= 0.3 and elevation > 0:
            alert = self._fire_alert(
                rule_id="pv_sunset",
                priority=AlertPriority.INFO,
                category="pv",
                title_de="Sonnenuntergang naht — PV-Restleistung nutzen",
                title_en="Sunset approaching — use remaining PV",
                message_de="Batterie aus PV-Restleistung laden bevor es dunkel wird.",
                message_en="Charge battery from remaining PV before dark.",
                action="charge",
                action_detail="charge_battery_from_pv",
                data={"pv_factor": pv_factor},
                cooldown_minutes=180,
            )
            if alert:
                alerts.append(alert)

        return alerts

    def evaluate_combined(
        self,
        warning_overview: dict | None = None,
        tariff_summary: dict | None = None,
        pv_factor: float = 0.0,
        solar_data: dict | None = None,
    ) -> list[ProactiveAlert]:
        """Run all evaluations and return new alerts."""
        all_alerts = []

        if warning_overview:
            all_alerts.extend(self.evaluate_weather(warning_overview))

        if tariff_summary:
            all_alerts.extend(self.evaluate_prices(tariff_summary))

        if solar_data:
            all_alerts.extend(self.evaluate_pv(pv_factor, solar_data))

        # Combined: severe weather + high price = critical
        if warning_overview and tariff_summary:
            highest_sev = warning_overview.get("highest_severity", 0)
            current_ct = tariff_summary.get("current_price_ct_kwh", 0)
            if highest_sev >= 3 and current_ct >= 30:
                alert = self._fire_alert(
                    rule_id="combined_weather_price",
                    priority=AlertPriority.CRITICAL,
                    category="combined",
                    title_de="Unwetter + hoher Strompreis",
                    title_en="Severe weather + high electricity price",
                    message_de="Batterie schützen, Verbrauch minimieren, auf Netzausfall vorbereiten.",
                    message_en="Protect battery, minimize consumption, prepare for outage.",
                    action="protect",
                    action_detail="protect_battery,minimize_consumption",
                    data={
                        "weather_severity": highest_sev,
                        "price_ct": current_ct,
                    },
                    cooldown_minutes=60,
                )
                if alert:
                    all_alerts.append(alert)

        self._last_evaluated = time.time()
        self._expire_old_alerts()
        return all_alerts

    def _expire_old_alerts(self) -> None:
        """Remove expired alerts."""
        now = datetime.now()
        self._alerts = [
            a
            for a in self._alerts
            if a.is_active
            and datetime.fromisoformat(a.expires_at) > now
        ]

    def get_active_alerts(self) -> list[ProactiveAlert]:
        """Get all active, non-expired alerts."""
        self._expire_old_alerts()
        return [a for a in self._alerts if a.is_active]

    def get_alerts_by_priority(self, min_priority: int = 1) -> list[ProactiveAlert]:
        """Get alerts at or above a priority level."""
        return [a for a in self.get_active_alerts() if a.priority >= min_priority]

    def get_summary(self) -> AlertSummary:
        """Get alert summary."""
        active = self.get_active_alerts()

        by_priority = {
            "info": sum(1 for a in active if a.priority == 1),
            "advisory": sum(1 for a in active if a.priority == 2),
            "warning": sum(1 for a in active if a.priority == 3),
            "critical": sum(1 for a in active if a.priority == 4),
        }

        by_category = {}
        for a in active:
            by_category[a.category] = by_category.get(a.category, 0) + 1

        highest = max((a.priority for a in active), default=0)

        return AlertSummary(
            total=len(active),
            by_priority=by_priority,
            by_category=by_category,
            highest_priority=highest,
            highest_priority_label=_PRIORITY_LABELS.get(highest, "Keine"),
            alerts=[asdict(a) for a in sorted(active, key=lambda x: -x.priority)],
            last_evaluated=datetime.fromtimestamp(self._last_evaluated).isoformat()
            if self._last_evaluated
            else "",
        )

    def dismiss_alert(self, alert_id: str) -> bool:
        """Dismiss/acknowledge an alert."""
        for a in self._alerts:
            if a.id == alert_id:
                a.is_active = False
                return True
        return False

    @property
    def alert_count(self) -> int:
        """Number of active alerts."""
        return len(self.get_active_alerts())
