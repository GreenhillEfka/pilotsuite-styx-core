"""German clarification prompts for voice intent disambiguation."""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


INTENT_LABELS = {
    "light.turn_on": "das Licht einschalten",
    "light.turn_off": "das Licht ausschalten",
    "light.set_brightness": "die Helligkeit ändern",
    "climate.set_temperature": "die Temperatur ändern",
    "scene.activate": "eine Szene aktivieren",
    "cover.open_cover": "den Rollladen öffnen",
    "cover.close_cover": "den Rollladen schließen",
}


ROOM_TEMPLATES = {
    "light.turn_on": "In welchem Raum soll ich das Licht einschalten?",
    "light.turn_off": "In welchem Raum soll ich das Licht ausschalten?",
    "light.set_brightness": "In welchem Raum soll ich die Helligkeit ändern?",
    "climate.set_temperature": "In welchem Raum soll ich die Temperatur ändern?",
    "cover.open_cover": "Welchen Rollladen soll ich öffnen?",
    "cover.close_cover": "Welchen Rollladen soll ich schließen?",
}


VALUE_TEMPLATES = {
    ("light.set_brightness", "brightness"): "Wie hell soll das Licht sein, zum Beispiel 50 Prozent?",
    ("climate.set_temperature", "target_temp"): "Auf wie viel Grad soll ich stellen?",
    ("scene.activate", "scene"): "Welche Szene soll ich aktivieren?",
}


MODE_TEMPLATES = {
    ("climate.set_temperature", "hvac_mode"): "Welchen Modus möchtest du, zum Beispiel Heizen, Kühlen oder Auto?",
}


GENERIC_TEMPLATE = "Kannst du bitte genauer sagen, was ich tun soll?"


def _room_phrase(slots: Dict[str, Any]) -> str:
    room = slots.get("room")
    return f" in {room}" if room else ""


def build_german_clarification(
    intent: str,
    missing_slots: Iterable[str],
    slots: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a German clarification question for missing slots."""
    slots = slots or {}
    missing = list(missing_slots)
    if not missing:
        return GENERIC_TEMPLATE

    slot_name = missing[0]

    if slot_name == "room":
        return ROOM_TEMPLATES.get(intent, "Für welchen Raum ist das gedacht?")

    if (intent, slot_name) == ("light.set_brightness", "brightness") and slots.get("room"):
        return f"Wie hell soll das Licht in {slots['room']} sein, zum Beispiel 50 Prozent?"

    if (intent, slot_name) == ("climate.set_temperature", "target_temp") and slots.get("room"):
        return f"Auf wie viel Grad soll ich die Temperatur in {slots['room']} stellen?"

    if (intent, slot_name) in VALUE_TEMPLATES:
        return VALUE_TEMPLATES[(intent, slot_name)]

    if (intent, slot_name) in MODE_TEMPLATES:
        return MODE_TEMPLATES[(intent, slot_name)]

    intent_label = INTENT_LABELS.get(intent, "die Aktion")
    return f"Ich habe verstanden, dass ich {intent_label} soll. Was genau fehlt noch?"
