"""P6-002: Lovelace Cards Complete — All 9 Symbiosis Entities + Extensions."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class CardType(Enum):
    """Lovelace card types."""
    ZONE_CARD = "zone_card"
    PRESENCE_CARD = "presence_card"
    HABITUS_CARD = "habitus_card"
    MUSIC_CARD = "music_card"
    ALARM_CARD = "alarm_card"
    ENERGY_CARD = "energy_card"
    WEATHER_CARD = "weather_card"
    CAMERA_CARD = "camera_card"
    CUSTOM_CARD = "custom_card"


@dataclass
class LovelaceCard:
    """Lovelace card definition."""
    id: str
    name: str
    card_type: CardType
    config: Dict[str, Any]
    entities: List[str] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)


class LovelaceCardGenerator:
    """Generates Lovelace cards for all entities."""

    def __init__(self):
        self._cards: Dict[str, LovelaceCard] = {}
        self._register_core_cards()

    def _register_core_cards(self):
        """Register core Lovelace cards."""
        # Zone Card
        self._cards["zone_card"] = LovelaceCard(
            id="zone_card",
            name="Zone Control",
            card_type=CardType.ZONE_CARD,
            config={
                "type": "custom:styx-zone-card",
                "title": "Zone",
                "show_habitat": True,
                "show_presence": True,
                "show_controls": True,
            },
            entities=["zone.living_room", "zone.bedroom", "zone.kitchen"]
        )
        
        # Presence Card
        self._cards["presence_card"] = LovelaceCard(
            id="presence_card",
            name="Presence Detection",
            card_type=CardType.PRESENCE_CARD,
            config={
                "type": "custom:styx-presence-card",
                "title": "Presence",
                "show_confidence": True,
                "show_history": True,
            },
            entities=["presence.home", "presence.away"]
        )
        
        # Habitus Card
        self._cards["habitus_card"] = LovelaceCard(
            id="habitus_card",
            name="Habitus Patterns",
            card_type=CardType.HABITUS_CARD,
            config={
                "type": "custom:styx-habitus-card",
                "title": "Habits",
                "show_patterns": True,
                "show_suggestions": True,
            },
            entities=["habitus.morning", "habitus.evening"]
        )
        
        # Music Card
        self._cards["music_card"] = LovelaceCard(
            id="music_card",
            name="Music Control",
            card_type=CardType.MUSIC_CARD,
            config={
                "type": "custom:styx-music-card",
                "title": "Music",
                "show_player": True,
                "show_playlist": True,
            },
            entities=["media_player.living_room", "media_player.bedroom"]
        )
        
        # Alarm Card
        self._cards["alarm_card"] = LovelaceCard(
            id="alarm_card",
            name="Alarm System",
            card_type=CardType.ALARM_CARD,
            config={
                "type": "custom:styx-alarm-card",
                "title": "Alarm",
                "show_status": True,
                "show_zones": True,
            },
            entities=["alarm_control_panel.home"]
        )
        
        # Energy Card
        self._cards["energy_card"] = LovelaceCard(
            id="energy_card",
            name="Energy Monitoring",
            card_type=CardType.ENERGY_CARD,
            config={
                "type": "custom:styx-energy-card",
                "title": "Energy",
                "show_consumption": True,
                "show_forecast": True,
            },
            entities=["sensor.energy_consumption", "sensor.energy_forecast"]
        )
        
        # Weather Card
        self._cards["weather_card"] = LovelaceCard(
            id="weather_card",
            name="Weather",
            card_type=CardType.WEATHER_CARD,
            config={
                "type": "custom:styx-weather-card",
                "title": "Weather",
                "show_forecast": True,
                "show_details": True,
            },
            entities=["weather.home"]
        )
        
        # Camera Card
        self._cards["camera_card"] = LovelaceCard(
            id="camera_card",
            name="Camera View",
            card_type=CardType.CAMERA_CARD,
            config={
                "type": "custom:styx-camera-card",
                "title": "Cameras",
                "show_live": True,
                "show_recordings": True,
            },
            entities=["camera.front_door", "camera.backyard"]
        )
        
        # Custom Card
        self._cards["custom_card"] = LovelaceCard(
            id="custom_card",
            name="Custom Card",
            card_type=CardType.CUSTOM_CARD,
            config={
                "type": "custom:styx-custom-card",
                "title": "Custom",
            },
            entities=[]
        )

    def get_card(self, card_id: str) -> Optional[LovelaceCard]:
        """Get card by ID."""
        return self._cards.get(card_id)

    def list_cards(self) -> List[LovelaceCard]:
        """List all cards."""
        return list(self._cards.values())

    def generate_yaml(self, card_id: str, entities: Optional[List[str]] = None) -> str:
        """Generate Lovelace YAML for a card."""
        card = self.get_card(card_id)
        if not card:
            return ""
        
        config = card.config.copy()
        if entities:
            config["entities"] = entities
        
        yaml_lines = []
        for key, value in config.items():
            if isinstance(value, dict):
                yaml_lines.append(f"{key}:")
                for k, v in value.items():
                    yaml_lines.append(f"  {k}: {v}")
            elif isinstance(value, list):
                yaml_lines.append(f"{key}:")
                for item in value:
                    yaml_lines.append(f"  - {item}")
            else:
                yaml_lines.append(f"{key}: {value}")
        
        return "\n".join(yaml_lines)

    def generate_dashboard(self, card_ids: List[str], title: str = "PilotSuite") -> Dict[str, Any]:
        """Generate complete dashboard config."""
        cards = []
        for card_id in card_ids:
            card = self.get_card(card_id)
            if card:
                cards.append(card.config)
        
        return {
            "title": title,
            "views": [
                {
                    "title": "Main",
                    "cards": cards
                }
            ]
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get card generator statistics."""
        return {
            "total_cards": len(self._cards),
            "card_types": list(set(c.card_type.value for c in self._cards.values())),
        }


# Global default card generator
default_card_generator: Optional[LovelaceCardGenerator] = None


def init_lovelace_cards() -> LovelaceCardGenerator:
    """Initialize global Lovelace card generator."""
    global default_card_generator
    default_card_generator = LovelaceCardGenerator()
    return default_card_generator
