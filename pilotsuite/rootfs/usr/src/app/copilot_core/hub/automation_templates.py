"""Automation Templates — AI-Generated Automation Blueprints (v6.9.0).

Features:
- Predefined automation templates for common scenarios
- Template variables with default values
- Condition/trigger/action structure matching HA automations
- Template categories (Licht, Klima, Sicherheit, Energie, Komfort)
- Blueprint generation for Home Assistant
- Template rating and popularity tracking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Data models ─────────────────────────────────────────────────────────────


@dataclass
class TemplateVariable:
    """A variable in an automation template."""

    name: str
    description_de: str
    description_en: str = ""
    var_type: str = "entity"  # entity, number, string, time, select
    default: str = ""
    options: list[str] = field(default_factory=list)
    required: bool = True


@dataclass
class AutomationTemplate:
    """An automation template / blueprint."""

    template_id: str
    name_de: str
    name_en: str
    description_de: str
    description_en: str = ""
    category: str = "comfort"  # lighting, climate, security, energy, comfort, presence
    icon: str = "mdi:robot"
    difficulty: str = "easy"  # easy, medium, advanced
    variables: list[TemplateVariable] = field(default_factory=list)
    triggers: list[dict[str, Any]] = field(default_factory=list)
    conditions: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    rating: float = 0.0
    usage_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class GeneratedAutomation:
    """A generated automation from a template."""

    automation_id: str
    template_id: str
    name: str
    variables: dict[str, str] = field(default_factory=dict)
    yaml_preview: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class TemplateSummary:
    """Summary of automation templates."""

    total_templates: int = 0
    categories: dict[str, int] = field(default_factory=dict)
    generated_count: int = 0
    popular: list[dict[str, Any]] = field(default_factory=list)


# ── Category definitions ───────────────────────────────────────────────────

_CATEGORIES: dict[str, dict[str, str]] = {
    "lighting": {"name_de": "Beleuchtung", "icon": "mdi:lightbulb-group"},
    "climate": {"name_de": "Klima & Heizung", "icon": "mdi:thermostat"},
    "security": {"name_de": "Sicherheit", "icon": "mdi:shield-home"},
    "energy": {"name_de": "Energie", "icon": "mdi:flash"},
    "comfort": {"name_de": "Komfort", "icon": "mdi:sofa"},
    "presence": {"name_de": "Anwesenheit", "icon": "mdi:account-check"},
}


# ── Built-in templates ────────────────────────────────────────────────────

_BUILTIN_TEMPLATES: list[dict[str, Any]] = [
    {
        "template_id": "light_motion",
        "name_de": "Licht bei Bewegung",
        "name_en": "Light on Motion",
        "description_de": "Schaltet Licht bei erkannter Bewegung ein und nach Ablauf einer Wartezeit wieder aus.",
        "description_en": "Turns on light when motion detected and off after timeout.",
        "category": "lighting",
        "icon": "mdi:motion-sensor",
        "difficulty": "easy",
        "variables": [
            {"name": "motion_sensor", "description_de": "Bewegungssensor", "var_type": "entity", "required": True},
            {"name": "light_entity", "description_de": "Licht-Entität", "var_type": "entity", "required": True},
            {"name": "timeout_min", "description_de": "Wartezeit (Minuten)", "var_type": "number", "default": "5"},
        ],
        "triggers": [{"platform": "state", "entity_id": "{{ motion_sensor }}", "to": "on"}],
        "conditions": [],
        "actions": [
            {"service": "light.turn_on", "target": {"entity_id": "{{ light_entity }}"}},
            {"delay": {"minutes": "{{ timeout_min }}"}},
            {"service": "light.turn_off", "target": {"entity_id": "{{ light_entity }}"}},
        ],
        "tags": ["motion", "light", "automatic"],
    },
    {
        "template_id": "night_lights",
        "name_de": "Nachtbeleuchtung",
        "name_en": "Night Lights",
        "description_de": "Dimmt Licht am Abend automatisch und schaltet es nachts aus.",
        "category": "lighting",
        "icon": "mdi:weather-night",
        "difficulty": "easy",
        "variables": [
            {"name": "light_entity", "description_de": "Licht-Entität", "var_type": "entity", "required": True},
            {"name": "dim_time", "description_de": "Dimmzeit", "var_type": "time", "default": "21:00"},
            {"name": "off_time", "description_de": "Ausschaltzeit", "var_type": "time", "default": "23:00"},
            {"name": "brightness", "description_de": "Helligkeit (%)", "var_type": "number", "default": "20"},
        ],
        "triggers": [{"platform": "time", "at": "{{ dim_time }}"}],
        "actions": [
            {"service": "light.turn_on", "target": {"entity_id": "{{ light_entity }}"}, "data": {"brightness_pct": "{{ brightness }}"}},
        ],
        "tags": ["night", "dim", "schedule"],
    },
    {
        "template_id": "heating_schedule",
        "name_de": "Heizplan Automatik",
        "name_en": "Heating Schedule",
        "description_de": "Regelt die Heizung nach Tageszeit — morgens warm, tagsüber reduziert, abends komfortabel.",
        "category": "climate",
        "icon": "mdi:radiator",
        "difficulty": "medium",
        "variables": [
            {"name": "climate_entity", "description_de": "Thermostat", "var_type": "entity", "required": True},
            {"name": "morning_temp", "description_de": "Morgentemperatur (°C)", "var_type": "number", "default": "21"},
            {"name": "day_temp", "description_de": "Tagestemperatur (°C)", "var_type": "number", "default": "19"},
            {"name": "evening_temp", "description_de": "Abendtemperatur (°C)", "var_type": "number", "default": "21"},
            {"name": "night_temp", "description_de": "Nachttemperatur (°C)", "var_type": "number", "default": "17"},
        ],
        "triggers": [{"platform": "time", "at": "06:00"}],
        "actions": [
            {"service": "climate.set_temperature", "target": {"entity_id": "{{ climate_entity }}"}, "data": {"temperature": "{{ morning_temp }}"}},
        ],
        "tags": ["heating", "schedule", "climate"],
    },
    {
        "template_id": "window_heating",
        "name_de": "Fenster offen → Heizung aus",
        "name_en": "Window Open → Heating Off",
        "description_de": "Schaltet die Heizung aus wenn ein Fenster geöffnet wird und wieder ein wenn es geschlossen wird.",
        "category": "climate",
        "icon": "mdi:window-open-variant",
        "difficulty": "easy",
        "variables": [
            {"name": "window_sensor", "description_de": "Fenstersensor", "var_type": "entity", "required": True},
            {"name": "climate_entity", "description_de": "Thermostat", "var_type": "entity", "required": True},
        ],
        "triggers": [{"platform": "state", "entity_id": "{{ window_sensor }}", "to": "on"}],
        "conditions": [],
        "actions": [
            {"service": "climate.turn_off", "target": {"entity_id": "{{ climate_entity }}"}},
        ],
        "tags": ["window", "heating", "energy-saving"],
    },
    {
        "template_id": "door_alert",
        "name_de": "Türalarm bei Abwesenheit",
        "name_en": "Door Alert When Away",
        "description_de": "Sendet Benachrichtigung wenn eine Tür geöffnet wird und niemand zu Hause ist.",
        "category": "security",
        "icon": "mdi:door-open",
        "difficulty": "medium",
        "variables": [
            {"name": "door_sensor", "description_de": "Türsensor", "var_type": "entity", "required": True},
            {"name": "presence_entity", "description_de": "Anwesenheitssensor", "var_type": "entity", "required": True},
            {"name": "notify_service", "description_de": "Benachrichtigungsdienst", "var_type": "string", "default": "notify.mobile_app"},
        ],
        "triggers": [{"platform": "state", "entity_id": "{{ door_sensor }}", "to": "on"}],
        "conditions": [{"condition": "state", "entity_id": "{{ presence_entity }}", "state": "not_home"}],
        "actions": [
            {"service": "{{ notify_service }}", "data": {"message": "Tür wurde geöffnet!", "title": "Sicherheitsalarm"}},
        ],
        "tags": ["door", "security", "notification"],
    },
    {
        "template_id": "energy_peak_alert",
        "name_de": "Spitzenverbrauch-Warnung",
        "name_en": "Peak Energy Alert",
        "description_de": "Warnt wenn der Stromverbrauch einen Schwellwert überschreitet.",
        "category": "energy",
        "icon": "mdi:flash-alert",
        "difficulty": "easy",
        "variables": [
            {"name": "power_sensor", "description_de": "Leistungssensor (W)", "var_type": "entity", "required": True},
            {"name": "threshold_w", "description_de": "Schwellwert (Watt)", "var_type": "number", "default": "3000"},
            {"name": "notify_service", "description_de": "Benachrichtigungsdienst", "var_type": "string", "default": "notify.mobile_app"},
        ],
        "triggers": [{"platform": "numeric_state", "entity_id": "{{ power_sensor }}", "above": "{{ threshold_w }}"}],
        "actions": [
            {"service": "{{ notify_service }}", "data": {"message": "Hoher Stromverbrauch erkannt!", "title": "Energie-Warnung"}},
        ],
        "tags": ["energy", "alert", "threshold"],
    },
    {
        "template_id": "welcome_home",
        "name_de": "Willkommen zu Hause",
        "name_en": "Welcome Home",
        "description_de": "Schaltet Licht und Musik ein wenn jemand nach Hause kommt.",
        "category": "presence",
        "icon": "mdi:home-heart",
        "difficulty": "medium",
        "variables": [
            {"name": "person_entity", "description_de": "Person", "var_type": "entity", "required": True},
            {"name": "light_entity", "description_de": "Licht", "var_type": "entity", "required": True},
            {"name": "media_player", "description_de": "Lautsprecher", "var_type": "entity", "default": ""},
        ],
        "triggers": [{"platform": "state", "entity_id": "{{ person_entity }}", "to": "home"}],
        "actions": [
            {"service": "light.turn_on", "target": {"entity_id": "{{ light_entity }}"}},
        ],
        "tags": ["presence", "welcome", "comfort"],
    },
    {
        "template_id": "goodnight",
        "name_de": "Gute-Nacht-Routine",
        "name_en": "Goodnight Routine",
        "description_de": "Schaltet alles aus, dimmt Flurbeleuchtung, setzt Nachtmodus.",
        "category": "comfort",
        "icon": "mdi:bed",
        "difficulty": "medium",
        "variables": [
            {"name": "all_lights_group", "description_de": "Alle Lichter (Gruppe)", "var_type": "entity", "required": True},
            {"name": "hallway_light", "description_de": "Flurlicht", "var_type": "entity", "default": ""},
            {"name": "media_players", "description_de": "Medien (Gruppe)", "var_type": "entity", "default": ""},
        ],
        "triggers": [{"platform": "time", "at": "23:00"}],
        "actions": [
            {"service": "light.turn_off", "target": {"entity_id": "{{ all_lights_group }}"}},
        ],
        "tags": ["goodnight", "routine", "sleep"],
    },
    {
        "template_id": "appliance_done",
        "name_de": "Gerät fertig — Benachrichtigung",
        "name_en": "Appliance Done Notification",
        "description_de": "Benachrichtigt wenn Waschmaschine oder Spülmaschine fertig ist (Leistung sinkt).",
        "category": "comfort",
        "icon": "mdi:washing-machine",
        "difficulty": "medium",
        "variables": [
            {"name": "power_sensor", "description_de": "Leistungssensor (W)", "var_type": "entity", "required": True},
            {"name": "threshold_w", "description_de": "Schwellwert Fertig (W)", "var_type": "number", "default": "5"},
            {"name": "notify_service", "description_de": "Benachrichtigungsdienst", "var_type": "string", "default": "notify.mobile_app"},
        ],
        "triggers": [{"platform": "numeric_state", "entity_id": "{{ power_sensor }}", "below": "{{ threshold_w }}", "for": "00:03:00"}],
        "actions": [
            {"service": "{{ notify_service }}", "data": {"message": "Gerät ist fertig!", "title": "Haushalt"}},
        ],
        "tags": ["appliance", "notification", "washing"],
    },
]


# ── Engine ──────────────────────────────────────────────────────────────────


class AutomationTemplateEngine:
    """Engine for AI-generated automation templates."""

    def __init__(self) -> None:
        self._templates: dict[str, AutomationTemplate] = {}
        self._generated: list[GeneratedAutomation] = []
        self._gen_counter: int = 0

        # Load built-in templates
        for t in _BUILTIN_TEMPLATES:
            variables = [TemplateVariable(**v) for v in t.get("variables", [])]
            template = AutomationTemplate(
                template_id=t["template_id"],
                name_de=t["name_de"],
                name_en=t.get("name_en", t["name_de"]),
                description_de=t["description_de"],
                description_en=t.get("description_en", ""),
                category=t.get("category", "comfort"),
                icon=t.get("icon", "mdi:robot"),
                difficulty=t.get("difficulty", "easy"),
                variables=variables,
                triggers=t.get("triggers", []),
                conditions=t.get("conditions", []),
                actions=t.get("actions", []),
                tags=t.get("tags", []),
            )
            self._templates[template.template_id] = template

    # ── Template query ───────────────────────────────────────────────────

    def get_templates(self, category: str | None = None,
                      difficulty: str | None = None,
                      search: str | None = None,
                      limit: int = 50) -> list[dict[str, Any]]:
        """Get automation templates with optional filters."""
        templates = list(self._templates.values())

        if category:
            templates = [t for t in templates if t.category == category]
        if difficulty:
            templates = [t for t in templates if t.difficulty == difficulty]
        if search:
            search_lower = search.lower()
            templates = [
                t for t in templates
                if search_lower in t.name_de.lower()
                or search_lower in t.description_de.lower()
                or any(search_lower in tag for tag in t.tags)
            ]

        templates.sort(key=lambda t: (-t.usage_count, -t.rating, t.name_de))

        return [
            {
                "template_id": t.template_id,
                "name_de": t.name_de,
                "name_en": t.name_en,
                "description_de": t.description_de,
                "category": t.category,
                "icon": t.icon,
                "difficulty": t.difficulty,
                "variable_count": len(t.variables),
                "tags": t.tags,
                "rating": t.rating,
                "usage_count": t.usage_count,
            }
            for t in templates[:limit]
        ]

    def get_template_detail(self, template_id: str) -> dict[str, Any] | None:
        """Get full template details including variables and actions."""
        t = self._templates.get(template_id)
        if not t:
            return None
        return {
            "template_id": t.template_id,
            "name_de": t.name_de,
            "name_en": t.name_en,
            "description_de": t.description_de,
            "category": t.category,
            "icon": t.icon,
            "difficulty": t.difficulty,
            "variables": [
                {
                    "name": v.name,
                    "description_de": v.description_de,
                    "var_type": v.var_type,
                    "default": v.default,
                    "options": v.options,
                    "required": v.required,
                }
                for v in t.variables
            ],
            "triggers": t.triggers,
            "conditions": t.conditions,
            "actions": t.actions,
            "tags": t.tags,
            "rating": t.rating,
            "usage_count": t.usage_count,
        }

    def get_categories(self) -> list[dict[str, Any]]:
        """Get template categories with counts."""
        counts: dict[str, int] = {}
        for t in self._templates.values():
            counts[t.category] = counts.get(t.category, 0) + 1
        return [
            {
                "category": cat,
                "name_de": _CATEGORIES.get(cat, {}).get("name_de", cat),
                "icon": _CATEGORIES.get(cat, {}).get("icon", "mdi:robot"),
                "count": count,
            }
            for cat, count in sorted(counts.items(), key=lambda x: -x[1])
        ]

    # ── Template generation ──────────────────────────────────────────────

    def generate_automation(self, template_id: str,
                            variables: dict[str, str],
                            name: str = "") -> GeneratedAutomation | None:
        """Generate an automation from a template with variable substitution."""
        template = self._templates.get(template_id)
        if not template:
            return None

        # Validate required variables
        for var in template.variables:
            if var.required and var.name not in variables:
                if var.default:
                    variables[var.name] = var.default
                else:
                    return None

        template.usage_count += 1
        self._gen_counter += 1
        auto_id = f"auto_{self._gen_counter}"

        # Generate YAML preview
        yaml_lines = [
            f"alias: {name or template.name_de}",
            "trigger:",
        ]
        for trigger in template.triggers:
            yaml_lines.append(f"  - platform: {trigger.get('platform', 'state')}")
            for k, v in trigger.items():
                if k != "platform":
                    resolved = self._resolve_var(str(v), variables)
                    yaml_lines.append(f"    {k}: {resolved}")

        if template.conditions:
            yaml_lines.append("condition:")
            for cond in template.conditions:
                yaml_lines.append(f"  - condition: {cond.get('condition', 'state')}")

        yaml_lines.append("action:")
        for action in template.actions:
            service = self._resolve_var(str(action.get("service", "")), variables)
            yaml_lines.append(f"  - service: {service}")

        yaml_preview = "\n".join(yaml_lines)

        gen = GeneratedAutomation(
            automation_id=auto_id,
            template_id=template_id,
            name=name or template.name_de,
            variables=variables,
            yaml_preview=yaml_preview,
        )
        self._generated.append(gen)
        return gen

    def _resolve_var(self, text: str, variables: dict[str, str]) -> str:
        """Replace {{ var }} placeholders with values."""
        for key, value in variables.items():
            text = text.replace("{{ " + key + " }}", value)
        return text

    # ── Rating ───────────────────────────────────────────────────────────

    def rate_template(self, template_id: str, rating: float) -> bool:
        """Rate a template (1-5 stars)."""
        template = self._templates.get(template_id)
        if not template or not (1 <= rating <= 5):
            return False
        # Running average
        if template.rating == 0:
            template.rating = rating
        else:
            template.rating = round((template.rating + rating) / 2, 1)
        return True

    # ── Custom templates ─────────────────────────────────────────────────

    def register_template(self, template_id: str, name_de: str,
                          description_de: str, category: str = "comfort",
                          **kwargs: Any) -> bool:
        """Register a custom template."""
        if template_id in self._templates:
            return False
        variables = [
            TemplateVariable(**v) for v in kwargs.pop("variables", [])
        ]
        self._templates[template_id] = AutomationTemplate(
            template_id=template_id,
            name_de=name_de,
            name_en=kwargs.pop("name_en", name_de),
            description_de=description_de,
            category=category if category in _CATEGORIES else "comfort",
            variables=variables,
            **kwargs,
        )
        return True

    # ── Summary ──────────────────────────────────────────────────────────

    def get_summary(self) -> TemplateSummary:
        """Get template summary."""
        categories: dict[str, int] = {}
        for t in self._templates.values():
            categories[t.category] = categories.get(t.category, 0) + 1

        popular = sorted(
            self._templates.values(),
            key=lambda t: (-t.usage_count, -t.rating),
        )[:5]

        return TemplateSummary(
            total_templates=len(self._templates),
            categories=categories,
            generated_count=len(self._generated),
            popular=[
                {
                    "template_id": t.template_id,
                    "name_de": t.name_de,
                    "icon": t.icon,
                    "usage_count": t.usage_count,
                    "rating": t.rating,
                }
                for t in popular
            ],
        )
