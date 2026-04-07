"""
Waste Collection Service -- Server-side waste context for PilotSuite Core.

Receives waste events from the HACS integration and provides:
- Waste status for LLM context injection
- Proactive TTS reminders via Supervisor API
- REST API endpoints for dashboard
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import requests

_LOGGER = logging.getLogger(__name__)

SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")


class WasteCollectionService:
    """Track waste collection state and deliver reminders."""

    def __init__(self):
        self._lock = threading.Lock()
        self._collections: List[Dict[str, Any]] = []
        self._last_event: Optional[Dict[str, Any]] = None
        self._last_update: float = 0
        _LOGGER.info("WasteCollectionService initialized")

    # ------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------

    def update_from_ha(self, data: dict) -> dict:
        """Update waste state from HA integration event."""
        with self._lock:
            self._last_event = data
            self._last_update = time.time()

            # Store waste types from event
            waste_types = data.get("waste_types", [])
            event_type = data.get("event_type", "")

            _LOGGER.info(
                "Waste event received: %s -- types=%s",
                event_type, waste_types,
            )

        return {"ok": True, "event_type": event_type, "types": waste_types}

    def update_collections(self, collections: list) -> dict:
        """Update full collection schedule from HA sensor data."""
        with self._lock:
            self._collections = collections
            self._last_update = time.time()
        return {"ok": True, "count": len(collections)}

    def get_status(self) -> dict:
        """Get current waste collection status."""
        with self._lock:
            today = [c for c in self._collections if c.get("days_to", 99) == 0]
            tomorrow = [c for c in self._collections if c.get("days_to", 99) == 1]
            return {
                "ok": True,
                "collections": self._collections,
                "today": [c.get("waste_type", "") for c in today],
                "tomorrow": [c.get("waste_type", "") for c in tomorrow],
                "next": self._collections[0] if self._collections else None,
                "total": len(self._collections),
                "last_update": self._last_update,
            }

    def get_context_for_llm(self) -> str:
        """Get waste context as text for LLM system prompt."""
        with self._lock:
            if not self._collections:
                return ""

            lines = ["Müllabfuhr-Status:"]
            for c in sorted(self._collections, key=lambda x: x.get("days_to", 99)):
                wtype = c.get("waste_type", "?")
                days = c.get("days_to", "?")
                if days == 0:
                    lines.append(f"  - {wtype}: HEUTE")
                elif days == 1:
                    lines.append(f"  - {wtype}: MORGEN")
                else:
                    lines.append(f"  - {wtype}: in {days} Tagen")
            return "\n".join(lines)

    # ------------------------------------------------------------------
    # Proactive Reminder (server-side TTS)
    # ------------------------------------------------------------------

    def deliver_reminder(self, message: str, tts_entity: str = "") -> dict:
        """Deliver a waste reminder via TTS and notification."""
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            return {"ok": False, "error": "No SUPERVISOR_TOKEN"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # TTS
        if tts_entity:
            try:
                requests.post(
                    f"{SUPERVISOR_API}/services/tts/speak",
                    json={"entity_id": tts_entity, "message": message, "cache": True},
                    headers=headers,
                    timeout=10,
                )
                _LOGGER.info("Waste TTS sent to %s", tts_entity)
            except Exception as exc:
                _LOGGER.warning("Waste TTS failed: %s", exc)

        # Persistent notification
        try:
            requests.post(
                f"{SUPERVISOR_API}/services/notify/persistent_notification",
                json={"message": message, "title": "Müllabfuhr"},
                headers=headers,
                timeout=10,
            )
        except Exception as exc:
            _LOGGER.warning("Waste notification failed: %s", exc)

        return {"ok": True, "method": "tts" if tts_entity else "notification"}


class BirthdayService:
    """Track birthday state and deliver reminders."""

    def __init__(self):
        self._lock = threading.Lock()
        self._birthdays: List[Dict[str, Any]] = []
        self._last_update: float = 0
        _LOGGER.info("BirthdayService initialized")

    def update_birthdays(self, birthdays: list) -> dict:
        """Update birthday list from HA integration."""
        with self._lock:
            self._birthdays = birthdays
            self._last_update = time.time()
        return {"ok": True, "count": len(birthdays)}

    def get_status(self) -> dict:
        """Get current birthday status."""
        with self._lock:
            today = [b for b in self._birthdays if b.get("days_until", 99) == 0]
            upcoming = [b for b in self._birthdays if 0 < b.get("days_until", 99) <= 14]
            return {
                "ok": True,
                "today": today,
                "upcoming": upcoming,
                "total": len(self._birthdays),
                "last_update": self._last_update,
            }

    def get_context_for_llm(self) -> str:
        """Get birthday context for LLM system prompt."""
        with self._lock:
            if not self._birthdays:
                return ""

            lines = []
            today = [b for b in self._birthdays if b.get("days_until", 99) == 0]
            if today:
                names = []
                for b in today:
                    n = b.get("name", "?")
                    age = b.get("age")
                    names.append(f"{n} ({age})" if age else n)
                lines.append(f"Heute Geburtstag: {', '.join(names)}")

            upcoming = [
                b for b in self._birthdays
                if 0 < b.get("days_until", 99) <= 7
            ]
            if upcoming:
                items = []
                for b in upcoming:
                    n = b.get("name", "?")
                    d = b.get("days_until", "?")
                    items.append(f"{n} in {d} Tagen")
                lines.append(f"Bevorstehende Geburtstage: {', '.join(items)}")

            return "\n".join(lines)

    def deliver_reminder(self, message: str, tts_entity: str = "") -> dict:
        """Deliver a birthday reminder via TTS and notification."""
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            return {"ok": False, "error": "No SUPERVISOR_TOKEN"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        if tts_entity:
            try:
                requests.post(
                    f"{SUPERVISOR_API}/services/tts/speak",
                    json={"entity_id": tts_entity, "message": message, "cache": True},
                    headers=headers,
                    timeout=10,
                )
            except Exception as exc:
                _LOGGER.warning("Birthday TTS failed: %s", exc)

        try:
            requests.post(
                f"{SUPERVISOR_API}/services/notify/persistent_notification",
                json={"message": message, "title": "Geburtstag"},
                headers=headers,
                timeout=10,
            )
        except Exception as exc:
            _LOGGER.warning("Birthday notification failed: %s", exc)

        return {"ok": True}
