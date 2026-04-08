"""Energy Advisor — Personalized Savings Recommendations (v6.8.0).

Features:
- Track energy consumption per device category
- Identify top consumers and savings opportunities
- Generate personalized recommendations (DE/EN)
- Tariff comparison with dynamic pricing awareness
- Weekly/monthly savings reports
- Eco-score per household with trend analysis
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class DeviceConsumption:
    """Energy consumption for a device/category."""

    entity_id: str
    name: str
    category: str  # lighting, heating, cooling, appliance, media, standby, ev, other
    daily_kwh: float = 0.0
    weekly_kwh: float = 0.0
    monthly_kwh: float = 0.0
    yearly_estimate_kwh: float = 0.0
    cost_monthly_eur: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class SavingsRecommendation:
    """A personalized savings recommendation."""

    rec_id: str
    title_de: str
    title_en: str
    description_de: str
    description_en: str
    category: str
    potential_savings_kwh: float = 0.0
    potential_savings_eur: float = 0.0
    difficulty: str = "easy"  # easy, medium, hard
    icon: str = "mdi:leaf"
    priority: int = 0
    applied: bool = False


@dataclass
class EcoScore:
    """Eco-score for a household."""

    score: int = 50  # 0-100
    trend: str = "stabil"  # steigend, fallend, stabil
    grade: str = "C"  # A+, A, B, C, D, E, F
    comparison_pct: int = 50  # percentile vs avg
    tips_count: int = 0


@dataclass
class ConsumptionBreakdown:
    """Breakdown of consumption by category."""

    category: str
    name_de: str
    icon: str
    kwh: float = 0.0
    pct: float = 0.0
    cost_eur: float = 0.0


@dataclass
class EnergyAdvisorDashboard:
    """Energy advisor dashboard overview."""

    total_daily_kwh: float = 0.0
    total_monthly_kwh: float = 0.0
    total_monthly_eur: float = 0.0
    eco_score: dict[str, Any] = field(default_factory=dict)
    breakdown: list[dict[str, Any]] = field(default_factory=list)
    top_consumers: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    savings_potential_eur: float = 0.0


# ── Category definitions ───────────────────────────────────────────────────

_CATEGORIES: dict[str, dict[str, str]] = {
    "lighting": {"name_de": "Beleuchtung", "icon": "mdi:lightbulb"},
    "heating": {"name_de": "Heizung", "icon": "mdi:radiator"},
    "cooling": {"name_de": "Kühlung", "icon": "mdi:snowflake"},
    "appliance": {"name_de": "Haushaltsgeräte", "icon": "mdi:washing-machine"},
    "media": {"name_de": "Medien & Unterhaltung", "icon": "mdi:television"},
    "standby": {"name_de": "Standby", "icon": "mdi:power-sleep"},
    "ev": {"name_de": "Elektrofahrzeug", "icon": "mdi:car-electric"},
    "other": {"name_de": "Sonstige", "icon": "mdi:flash"},
}

# ── Built-in recommendations ──────────────────────────────────────────────

_BUILTIN_RECOMMENDATIONS: list[dict[str, Any]] = [
    {
        "rec_id": "standby_killer",
        "title_de": "Standby-Verbrauch eliminieren",
        "title_en": "Eliminate standby consumption",
        "description_de": "Geräte im Standby verbrauchen bis zu 10% des Gesamtstroms. Schaltbare Steckdosen nutzen.",
        "description_en": "Standby devices consume up to 10% of total electricity. Use switchable outlets.",
        "category": "standby",
        "potential_savings_kwh": 300,
        "potential_savings_eur": 90,
        "difficulty": "easy",
        "icon": "mdi:power-plug-off",
        "priority": 90,
    },
    {
        "rec_id": "led_upgrade",
        "title_de": "LED-Beleuchtung optimieren",
        "title_en": "Optimize LED lighting",
        "description_de": "Glühbirnen durch LEDs ersetzen spart bis zu 80% Lichtenergie.",
        "description_en": "Replacing bulbs with LEDs saves up to 80% of lighting energy.",
        "category": "lighting",
        "potential_savings_kwh": 200,
        "potential_savings_eur": 60,
        "difficulty": "easy",
        "icon": "mdi:lightbulb-on",
        "priority": 85,
    },
    {
        "rec_id": "heating_schedule",
        "title_de": "Heizplan optimieren",
        "title_en": "Optimize heating schedule",
        "description_de": "Nachtabsenkung und Abwesenheitserkennung können 15-25% Heizenergie sparen.",
        "description_en": "Night setback and absence detection can save 15-25% heating energy.",
        "category": "heating",
        "potential_savings_kwh": 500,
        "potential_savings_eur": 150,
        "difficulty": "medium",
        "icon": "mdi:thermometer-low",
        "priority": 95,
    },
    {
        "rec_id": "washing_offpeak",
        "title_de": "Waschen in Nebenzeiten",
        "title_en": "Wash during off-peak hours",
        "description_de": "Waschmaschine und Trockner in Niedertarifzeiten nutzen.",
        "description_en": "Use washing machine and dryer during low-tariff hours.",
        "category": "appliance",
        "potential_savings_kwh": 100,
        "potential_savings_eur": 30,
        "difficulty": "easy",
        "icon": "mdi:washing-machine",
        "priority": 70,
    },
    {
        "rec_id": "ev_smart_charge",
        "title_de": "E-Auto intelligent laden",
        "title_en": "Smart EV charging",
        "description_de": "E-Auto bei niedrigen Strompreisen oder mit PV-Überschuss laden.",
        "description_en": "Charge EV during low prices or with PV surplus.",
        "category": "ev",
        "potential_savings_kwh": 400,
        "potential_savings_eur": 120,
        "difficulty": "medium",
        "icon": "mdi:ev-station",
        "priority": 80,
    },
    {
        "rec_id": "cooling_efficiency",
        "title_de": "Kühlung effizienter nutzen",
        "title_en": "Use cooling more efficiently",
        "description_de": "Temperatur um 1°C höher einstellen spart 6% Kühlenergie.",
        "description_en": "Setting temperature 1°C higher saves 6% cooling energy.",
        "category": "cooling",
        "potential_savings_kwh": 150,
        "potential_savings_eur": 45,
        "difficulty": "easy",
        "icon": "mdi:snowflake-thermometer",
        "priority": 65,
    },
    {
        "rec_id": "media_auto_off",
        "title_de": "Mediengeräte automatisch ausschalten",
        "title_en": "Auto-off media devices",
        "description_de": "TV und Receiver nach Inaktivität automatisch ausschalten.",
        "description_en": "Turn off TV and receiver after inactivity.",
        "category": "media",
        "potential_savings_kwh": 80,
        "potential_savings_eur": 24,
        "difficulty": "easy",
        "icon": "mdi:television-off",
        "priority": 60,
    },
]


# ── Engine ──────────────────────────────────────────────────────────────────


class EnergyAdvisorEngine:
    """Engine for personalized energy savings recommendations."""

    def __init__(self, electricity_price_ct_kwh: float = 30.0) -> None:
        self._price_ct_kwh = electricity_price_ct_kwh
        self._devices: dict[str, DeviceConsumption] = {}
        self._recommendations: list[SavingsRecommendation] = [
            SavingsRecommendation(**r) for r in _BUILTIN_RECOMMENDATIONS
        ]
        self._eco_history: list[tuple[datetime, int]] = []

    # ── Device tracking ──────────────────────────────────────────────────

    def register_device(self, entity_id: str, name: str,
                        category: str = "other") -> DeviceConsumption:
        """Register a device for energy tracking."""
        device = DeviceConsumption(
            entity_id=entity_id,
            name=name,
            category=category if category in _CATEGORIES else "other",
        )
        self._devices[entity_id] = device
        return device

    def update_consumption(self, entity_id: str, daily_kwh: float) -> bool:
        """Update daily consumption for a device."""
        device = self._devices.get(entity_id)
        if not device:
            return False
        device.daily_kwh = daily_kwh
        device.weekly_kwh = daily_kwh * 7
        device.monthly_kwh = daily_kwh * 30
        device.yearly_estimate_kwh = daily_kwh * 365
        device.cost_monthly_eur = device.monthly_kwh * self._price_ct_kwh / 100
        device.last_updated = datetime.now(tz=timezone.utc)
        return True

    def set_electricity_price(self, ct_kwh: float) -> None:
        """Update electricity price (ct/kWh)."""
        self._price_ct_kwh = ct_kwh
        # Recalculate all costs
        for device in self._devices.values():
            device.cost_monthly_eur = device.monthly_kwh * self._price_ct_kwh / 100

    # ── Analysis ─────────────────────────────────────────────────────────

    def get_breakdown(self) -> list[ConsumptionBreakdown]:
        """Get consumption breakdown by category."""
        category_kwh: dict[str, float] = defaultdict(float)
        for device in self._devices.values():
            category_kwh[device.category] += device.monthly_kwh

        total = sum(category_kwh.values()) or 1.0
        result = []
        for cat, kwh in sorted(category_kwh.items(), key=lambda x: -x[1]):
            cat_info = _CATEGORIES.get(cat, _CATEGORIES["other"])
            result.append(ConsumptionBreakdown(
                category=cat,
                name_de=cat_info["name_de"],
                icon=cat_info["icon"],
                kwh=round(kwh, 1),
                pct=round(kwh / total * 100, 1),
                cost_eur=round(kwh * self._price_ct_kwh / 100, 2),
            ))
        return result

    def get_top_consumers(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get top energy consuming devices."""
        sorted_devices = sorted(
            self._devices.values(),
            key=lambda d: d.monthly_kwh,
            reverse=True,
        )
        return [
            {
                "entity_id": d.entity_id,
                "name": d.name,
                "category": d.category,
                "daily_kwh": round(d.daily_kwh, 2),
                "monthly_kwh": round(d.monthly_kwh, 1),
                "cost_monthly_eur": round(d.cost_monthly_eur, 2),
            }
            for d in sorted_devices[:limit]
        ]

    def calculate_eco_score(self) -> EcoScore:
        """Calculate household eco-score."""
        if not self._devices:
            return EcoScore()

        total_monthly = sum(d.monthly_kwh for d in self._devices.values())

        # Simple scoring: lower consumption = higher score
        # Average German household: ~3500 kWh/year = ~292 kWh/month
        avg_monthly = 292.0
        ratio = total_monthly / avg_monthly if avg_monthly > 0 else 1.0

        if ratio <= 0.5:
            score = 95
        elif ratio <= 0.7:
            score = 85
        elif ratio <= 0.9:
            score = 75
        elif ratio <= 1.0:
            score = 65
        elif ratio <= 1.2:
            score = 50
        elif ratio <= 1.5:
            score = 35
        else:
            score = 20

        # Grade
        if score >= 90:
            grade = "A+"
        elif score >= 80:
            grade = "A"
        elif score >= 70:
            grade = "B"
        elif score >= 60:
            grade = "C"
        elif score >= 45:
            grade = "D"
        elif score >= 30:
            grade = "E"
        else:
            grade = "F"

        # Trend
        now = datetime.now(tz=timezone.utc)
        self._eco_history.append((now, score))
        # Keep last 30 entries
        self._eco_history = self._eco_history[-30:]

        trend = "stabil"
        if len(self._eco_history) >= 3:
            recent = [s for _, s in self._eco_history[-3:]]
            older = [s for _, s in self._eco_history[:3]]
            avg_recent = sum(recent) / len(recent)
            avg_older = sum(older) / len(older)
            if avg_recent - avg_older > 5:
                trend = "steigend"
            elif avg_older - avg_recent > 5:
                trend = "fallend"

        comparison = min(100, max(0, int((1 - ratio + 0.5) * 100)))

        applied = sum(1 for r in self._recommendations if r.applied)

        return EcoScore(
            score=score,
            trend=trend,
            grade=grade,
            comparison_pct=comparison,
            tips_count=applied,
        )

    # ── Recommendations ──────────────────────────────────────────────────

    def get_recommendations(self, category: str | None = None,
                            limit: int = 10) -> list[dict[str, Any]]:
        """Get personalized savings recommendations."""
        recs = self._recommendations
        if category:
            recs = [r for r in recs if r.category == category]

        # Sort by priority (highest first), unapplied first
        recs = sorted(recs, key=lambda r: (-int(not r.applied), -r.priority))

        return [
            {
                "rec_id": r.rec_id,
                "title_de": r.title_de,
                "title_en": r.title_en,
                "description_de": r.description_de,
                "category": r.category,
                "potential_savings_kwh": r.potential_savings_kwh,
                "potential_savings_eur": r.potential_savings_eur,
                "difficulty": r.difficulty,
                "icon": r.icon,
                "applied": r.applied,
            }
            for r in recs[:limit]
        ]

    def mark_recommendation_applied(self, rec_id: str) -> bool:
        """Mark a recommendation as applied."""
        for rec in self._recommendations:
            if rec.rec_id == rec_id:
                rec.applied = True
                return True
        return False

    def add_recommendation(self, rec_id: str, title_de: str, title_en: str = "",
                           description_de: str = "", description_en: str = "",
                           category: str = "other", **kwargs: Any) -> bool:
        """Add a custom recommendation."""
        if any(r.rec_id == rec_id for r in self._recommendations):
            return False
        self._recommendations.append(SavingsRecommendation(
            rec_id=rec_id,
            title_de=title_de,
            title_en=title_en or title_de,
            description_de=description_de,
            description_en=description_en or description_de,
            category=category,
            **kwargs,
        ))
        return True

    # ── Dashboard ────────────────────────────────────────────────────────

    def get_dashboard(self) -> EnergyAdvisorDashboard:
        """Get energy advisor dashboard."""
        total_daily = sum(d.daily_kwh for d in self._devices.values())
        total_monthly = sum(d.monthly_kwh for d in self._devices.values())
        total_cost = total_monthly * self._price_ct_kwh / 100

        eco = self.calculate_eco_score()
        breakdown = self.get_breakdown()
        top_consumers = self.get_top_consumers(5)
        recs = self.get_recommendations(limit=5)

        savings = sum(r["potential_savings_eur"] for r in recs if not r["applied"])

        return EnergyAdvisorDashboard(
            total_daily_kwh=round(total_daily, 2),
            total_monthly_kwh=round(total_monthly, 1),
            total_monthly_eur=round(total_cost, 2),
            eco_score={
                "score": eco.score,
                "grade": eco.grade,
                "trend": eco.trend,
                "comparison_pct": eco.comparison_pct,
                "tips_applied": eco.tips_count,
            },
            breakdown=[
                {
                    "category": b.category,
                    "name_de": b.name_de,
                    "icon": b.icon,
                    "kwh": b.kwh,
                    "pct": b.pct,
                    "cost_eur": b.cost_eur,
                }
                for b in breakdown
            ],
            top_consumers=top_consumers,
            recommendations=recs,
            savings_potential_eur=round(savings, 2),
        )
