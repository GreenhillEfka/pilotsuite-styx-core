"""Rule Templates — Vordefinierte Automation-Templates pro Zone-Typ (SOTA 2026).

Zone-Typen:
- living (Wohnzimmer)
- bath (Bad)
- kitchen (Küche)
- bedroom (Schlafzimmer)
- office (Büro)
- hallway (Flur)
- outdoor (Außen)

Jeder Zone-Typ hat vordefinierte Templates für:
- Light Automation
- Climate Automation
- Security Automation
- Energy Automation

Features:
- Template Selection pro Zone
- Auto-Configuration basierend auf verfügbaren Neuronen
- Customization der Templates
- Template → Rule Conversion
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum
import threading

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# ZONE TYPES
# =============================================================================

class ZoneType(str, Enum):
    """Zone Typen."""
    
    LIVING = "living"
    BATH = "bath"
    KITCHEN = "kitchen"
    BEDROOM = "bedroom"
    OFFICE = "office"
    HALLWAY = "hallway"
    OUTDOOR = "outdoor"


# =============================================================================
# RULE TEMPLATES
# =============================================================================

@dataclass
class RuleTemplate:
    """Automation Rule Template."""
    
    template_id: str
    name: str
    description: str
    zone_types: List[ZoneType]
    module: str
    trigger: Dict[str, Any]
    condition: Dict[str, Any] = field(default_factory=dict)
    action: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    energy_impact: float = 0.0  # Estimated energy impact (-1 to 1)
    comfort_impact: float = 0.0  # Estimated comfort impact (0 to 1)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def instantiate(
        self,
        zone_id: str,
        custom_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Template instanziieren für konkrete Zone."""
        params = {**self.parameters, **(custom_params or {})}
        
        # Substitute parameters in trigger/action
        trigger = self._substitute_params(self.trigger, params)
        action = self._substitute_params(self.action, params)
        
        return {
            "name": self.name,
            "description": self.description,
            "zone_id": zone_id,
            "trigger": trigger,
            "condition": self.condition,
            "action": action,
            "metadata": {
                "template_id": self.template_id,
                "energy_impact": self.energy_impact,
                "comfort_impact": self.comfort_impact,
            },
        }
    
    def _substitute_params(self, data: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Parameter in Template ersetzen."""
        import json
        data_str = json.dumps(data)
        
        for key, value in params.items():
            data_str = data_str.replace(f"{{{{{key}}}}}", str(value))
        
        return json.loads(data_str)


# =============================================================================
# TEMPLATE LIBRARY
# =============================================================================

class RuleTemplateLibrary:
    """Bibliothek für Rule Templates."""
    
    # Default Templates pro Zone-Typ
    DEFAULT_TEMPLATES: List[RuleTemplate] = [
        # === LIVING ROOM TEMPLATES ===
        RuleTemplate(
            template_id="living_light_presence",
            name="Wohnzimmer Licht bei Präsenz",
            description="Licht automatisch einschalten wenn Präsenz erkannt und Helligkeit zu gering",
            zone_types=[ZoneType.LIVING],
            module="light",
            trigger={
                "presence": True,
                "brightness_below": "{{brightness_threshold}}",
            },
            action={
                "module": "light",
                "command": "turn_on",
                "parameters": {"brightness_pct": "{{brightness_pct}}"},
            },
            parameters={
                "brightness_threshold": 0.3,
                "brightness_pct": 40,
            },
            energy_impact=-0.2,
            comfort_impact=0.8,
        ),
        RuleTemplate(
            template_id="living_light_no_presence",
            name="Wohnzimmer Licht aus nach Präsenz-Ende",
            description="Licht automatisch ausschalten nach 5 Min keine Präsenz",
            zone_types=[ZoneType.LIVING],
            module="light",
            trigger={
                "no_presence_duration_s": 300,
            },
            action={
                "module": "light",
                "command": "turn_off",
            },
            parameters={},
            energy_impact=0.3,
            comfort_impact=0.1,
        ),
        RuleTemplate(
            template_id="living_mood_light",
            name="Wohnzimmer Stimmungs-Licht",
            description="Lichtfarbe und Helligkeit basierend auf Stimmung",
            zone_types=[ZoneType.LIVING],
            module="light",
            trigger={
                "mood_change": True,
            },
            condition={
                "mood_dimension": "valence",
            },
            action={
                "module": "light",
                "command": "set_scene",
                "parameters": {
                    "scene": "{{mood_scene}}",
                    "brightness_pct": "{{mood_brightness}}",
                },
            },
            parameters={
                "mood_scene": "relax",
                "mood_brightness": 30,
            },
            energy_impact=-0.1,
            comfort_impact=0.9,
        ),
        
        # === BATHROOM TEMPLATES ===
        RuleTemplate(
            template_id="bath_light_motion",
            name="Bad Licht bei Bewegung",
            description="Licht einschalten bei Bewegung im Bad",
            zone_types=[ZoneType.BATH],
            module="light",
            trigger={
                "motion": True,
            },
            action={
                "module": "light",
                "command": "turn_on",
                "parameters": {"brightness_pct": 80},
            },
            parameters={},
            energy_impact=-0.1,
            comfort_impact=0.7,
        ),
        RuleTemplate(
            template_id="bath_light_timeout",
            name="Bad Licht Timeout",
            description="Licht nach 2 Min automatisch ausschalten",
            zone_types=[ZoneType.BATH],
            module="light",
            trigger={
                "no_motion_duration_s": 120,
            },
            action={
                "module": "light",
                "command": "turn_off",
            },
            parameters={},
            energy_impact=0.2,
            comfort_impact=0.1,
        ),
        
        # === KITCHEN TEMPLATES ===
        RuleTemplate(
            template_id="kitchen_light_daytime",
            name="Küche Licht tageszeitabhängig",
            description="Licht nur bei Dunkelheit einschalten",
            zone_types=[ZoneType.KITCHEN],
            module="light",
            trigger={
                "presence": True,
                "time_of_day": ["evening", "night"],
            },
            action={
                "module": "light",
                "command": "turn_on",
                "parameters": {"brightness_pct": 60},
            },
            parameters={},
            energy_impact=0.2,
            comfort_impact=0.5,
        ),
        
        # === BEDROOM TEMPLATES ===
        RuleTemplate(
            template_id="bedroom_light_evening",
            name="Schlafzimmer Abend-Licht",
            description="Warmes Licht am Abend",
            zone_types=[ZoneType.BEDROOM],
            module="light",
            trigger={
                "presence": True,
                "time_of_day": "evening",
            },
            action={
                "module": "light",
                "command": "turn_on",
                "parameters": {
                    "brightness_pct": 30,
                    "color_temp": "warm",
                },
            },
            parameters={},
            energy_impact=-0.1,
            comfort_impact=0.8,
        ),
        RuleTemplate(
            template_id="bedroom_light_off_bedtime",
            name="Schlafzimmer Licht zur Bettzeit",
            description="Licht zur Bettzeit automatisch ausschalten",
            zone_types=[ZoneType.BEDROOM],
            module="light",
            trigger={
                "time_is": "23:00",
            },
            action={
                "module": "light",
                "command": "turn_off",
            },
            parameters={},
            energy_impact=0.2,
            comfort_impact=0.3,
        ),
        
        # === OFFICE TEMPLATES ===
        RuleTemplate(
            template_id="office_light_workday",
            name="Büro Licht an Werktagen",
            description="Licht nur an Werktagen während Arbeitszeit",
            zone_types=[ZoneType.OFFICE],
            module="light",
            trigger={
                "presence": True,
                "day_of_week": ["mon", "tue", "wed", "thu", "fri"],
                "time_range": ["08:00", "18:00"],
            },
            action={
                "module": "light",
                "command": "turn_on",
                "parameters": {"brightness_pct": 80},
            },
            parameters={},
            energy_impact=0.3,
            comfort_impact=0.6,
        ),
        
        # === HALLWAY TEMPLATES ===
        RuleTemplate(
            template_id="hallway_light_motion",
            name="Flur Licht bei Bewegung",
            description="Licht bei Bewegung im Flur",
            zone_types=[ZoneType.HALLWAY],
            module="light",
            trigger={
                "motion": True,
            },
            action={
                "module": "light",
                "command": "turn_on",
                "parameters": {"brightness_pct": 50},
            },
            parameters={},
            energy_impact=-0.1,
            comfort_impact=0.6,
        ),
        RuleTemplate(
            template_id="hallway_light_quick_off",
            name="Flur Licht schnell aus",
            description="Licht nach 30 Sek keine Bewegung ausschalten",
            zone_types=[ZoneType.HALLWAY],
            module="light",
            trigger={
                "no_motion_duration_s": 30,
            },
            action={
                "module": "light",
                "command": "turn_off",
            },
            parameters={},
            energy_impact=0.3,
            comfort_impact=0.1,
        ),
        
        # === OUTDOOR TEMPLATES ===
        RuleTemplate(
            template_id="outdoor_light_sunset",
            name="Außen Licht bei Sonnenuntergang",
            description="Außenbeleuchtung bei Sonnenuntergang einschalten",
            zone_types=[ZoneType.OUTDOOR],
            module="light",
            trigger={
                "sun_event": "sunset",
                "offset_minutes": 15,
            },
            action={
                "module": "light",
                "command": "turn_on",
            },
            parameters={},
            energy_impact=-0.2,
            comfort_impact=0.5,
        ),
        RuleTemplate(
            template_id="outdoor_light_sunrise",
            name="Außen Licht bei Sonnenaufgang",
            description="Außenbeleuchtung bei Sonnenaufgang ausschalten",
            zone_types=[ZoneType.OUTDOOR],
            module="light",
            trigger={
                "sun_event": "sunrise",
            },
            action={
                "module": "light",
                "command": "turn_off",
            },
            parameters={},
            energy_impact=0.2,
            comfort_impact=0.1,
        ),
    ]
    
    def __init__(self):
        self._templates: Dict[str, RuleTemplate] = {}
        self._lock = threading.Lock()
        
        # Initialize with defaults
        for template in self.DEFAULT_TEMPLATES:
            self._templates[template.template_id] = template
        
        _LOGGER.info(f"RuleTemplateLibrary initialized with {len(self._templates)} templates")
    
    def get_templates_for_zone_type(self, zone_type: ZoneType) -> List[RuleTemplate]:
        """Templates für Zone-Typ holen."""
        with self._lock:
            return [
                t for t in self._templates.values()
                if zone_type in t.zone_types
            ]
    
    def get_template(self, template_id: str) -> Optional[RuleTemplate]:
        """Template nach ID holen."""
        with self._lock:
            return self._templates.get(template_id)
    
    def instantiate_template(
        self,
        template_id: str,
        zone_id: str,
        custom_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Template instanziieren."""
        template = self.get_template(template_id)
        if not template:
            return None
        
        return template.instantiate(zone_id, custom_params)
    
    def get_recommended_templates(
        self,
        zone_type: ZoneType,
        available_neurons: List[str],
    ) -> List[RuleTemplate]:
        """Empfohlene Templates basierend auf verfügbaren Neuronen."""
        templates = self.get_templates_for_zone_type(zone_type)
        
        # Filter templates based on available neurons
        compatible = []
        for template in templates:
            required_neurons = self._get_required_neurons(template)
            if all(rn in available_neurons for rn in required_neurons):
                compatible.append(template)
        
        # Sort by comfort impact (descending)
        compatible.sort(key=lambda t: t.comfort_impact, reverse=True)
        
        return compatible
    
    def _get_required_neurons(self, template: RuleTemplate) -> List[str]:
        """Benötigte Neuronen für Template."""
        neurons = []
        
        trigger = template.trigger
        if "presence" in trigger or "motion" in trigger:
            neurons.append("presence")
        if "brightness_below" in trigger:
            neurons.append("brightness")
        if "time_of_day" in trigger or "time_is" in trigger:
            neurons.append("time")
        if "mood_change" in trigger:
            neurons.append("mood")
        if "sun_event" in trigger:
            neurons.append("time")
        
        return neurons
    
    def add_custom_template(self, template: RuleTemplate) -> None:
        """Custom Template hinzufügen."""
        with self._lock:
            self._templates[template.template_id] = template
            _LOGGER.info(f"Added custom template: {template.template_id}")
    
    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_templates": len(self._templates),
                "by_zone_type": self._count_by_zone_type(),
                "avg_energy_impact": sum(t.energy_impact for t in self._templates.values()) / len(self._templates),
                "avg_comfort_impact": sum(t.comfort_impact for t in self._templates.values()) / len(self._templates),
            }
    
    def _count_by_zone_type(self) -> Dict[str, int]:
        """Count templates by zone type."""
        counts: Dict[str, int] = {}
        for template in self._templates.values():
            for zone_type in template.zone_types:
                counts[zone_type.value] = counts.get(zone_type.value, 0) + 1
        return counts


# =============================================================================
# Singleton
# =============================================================================

_library_instance: Optional[RuleTemplateLibrary] = None


def get_rule_template_library() -> RuleTemplateLibrary:
    """Singleton-Zugriff."""
    global _library_instance
    
    if _library_instance is None:
        _library_instance = RuleTemplateLibrary()
    
    return _library_instance
