"""
Automation Creator -- Convert accepted suggestions into real HA automations.

Uses the Home Assistant Supervisor REST API to create automation configurations.
Each created automation is tagged with ``pilotsuite_styx`` so it can be
identified and listed later.

Trigger/action parsing is intentionally simple (keyword-based) so that it
works without an LLM round-trip.  Complex suggestions that cannot be parsed
deterministically are returned with ``ok: False`` and a descriptive error.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

import requests

_LOGGER = logging.getLogger(__name__)

# Supervisor REST API base URL (set by the HA add-on environment)
_SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")

# Tag used to mark automations created by Styx / PilotSuite
STYX_TAG = "pilotsuite_styx"


class AutomationCreator:
    """Create real Home Assistant automations from accepted suggestions.

    This class is thread-safe.  All HTTP calls go through the HA Supervisor
    REST API using the ``SUPERVISOR_TOKEN`` environment variable.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._created: List[Dict[str, Any]] = []
        _LOGGER.info("AutomationCreator initialized")

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_headers() -> Dict[str, str]:
        """Build Authorization headers for the Supervisor API."""
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _has_token() -> bool:
        return bool(os.environ.get("SUPERVISOR_TOKEN", "").strip())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_from_suggestion(self, suggestion: dict) -> dict:
        """Convert a suggestion dict into a real HA automation.

        Accepts either natural-language or pre-parsed structured data::

            # Natural language (regex-parsed):
            {"antecedent": "When the sun sets", "consequent": "Turn on light.living_room"}

            # Pre-parsed (from LLM tool call, bypasses regex):
            {"alias": "Sunset lights",
             "trigger": [{"platform": "sun", "event": "sunset"}],
             "action":  [{"service": "light.turn_on", "target": {"entity_id": "light.living_room"}}]}

        Returns a result dict with ``ok: True/False`` and details.
        """
        if not self._has_token():
            return {
                "ok": False,
                "error": "No SUPERVISOR_TOKEN -- HA automation API unavailable",
            }

        # Path 1: Pre-parsed structured trigger/action (from LLM tool calls)
        if suggestion.get("trigger") and suggestion.get("action"):
            trigger = suggestion["trigger"]
            if not isinstance(trigger, list):
                trigger = [trigger]
            action = suggestion["action"]
            if not isinstance(action, list):
                action = [action]
            alias = suggestion.get("alias", "PilotSuite Automation")
            antecedent = suggestion.get("antecedent", alias)
            consequent = suggestion.get("consequent", alias)
        else:
            # Path 2: Natural language (regex-parsed)
            antecedent = (suggestion.get("antecedent") or "").strip()
            consequent = (suggestion.get("consequent") or "").strip()

            if not antecedent or not consequent:
                return {
                    "ok": False,
                    "error": "Both 'antecedent' and 'consequent' are required",
                }

            alias = (
                suggestion.get("alias")
                or f"PilotSuite: {antecedent[:40]} -> {consequent[:40]}"
            )

            try:
                trigger = self._build_trigger(antecedent)
            except ValueError as exc:
                return {"ok": False, "error": f"Cannot parse trigger: {exc}"}

            try:
                action = self._build_action(consequent)
            except ValueError as exc:
                return {"ok": False, "error": f"Cannot parse action: {exc}"}

        # Build HA automation config
        automation_id = f"styx_{uuid.uuid4().hex[:12]}"

        config = {
            "id": automation_id,
            "alias": alias,
            "description": f"Created by PilotSuite Styx from suggestion. "
                           f"Antecedent: {antecedent} | Consequent: {consequent}",
            "trigger": trigger,
            "action": action,
            "mode": "single",
            "tags": [STYX_TAG],
        }

        # POST to Supervisor API
        url = f"{_SUPERVISOR_API}/config/automation/config/{automation_id}"
        try:
            resp = requests.post(
                url, json=config, headers=self._get_headers(), timeout=15,
            )
            if resp.ok:
                record = {
                    "automation_id": automation_id,
                    "alias": alias,
                    "created_at": time.time(),
                    "antecedent": antecedent,
                    "consequent": consequent,
                }
                with self._lock:
                    self._created.append(record)
                _LOGGER.info(
                    "Created automation %s: %s", automation_id, alias,
                )
                return {"ok": True, "automation_id": automation_id, "alias": alias}
            else:
                body = resp.text[:300]
                _LOGGER.error(
                    "HA API returned %s for automation %s: %s",
                    resp.status_code, automation_id, body,
                )
                return {
                    "ok": False,
                    "error": f"HA API error ({resp.status_code})",
                    "detail": body,
                }
        except requests.RequestException as exc:
            _LOGGER.exception("HTTP error creating automation %s", automation_id)
            return {"ok": False, "error": f"HTTP request failed: {exc}"}

    def list_created(self) -> list:
        """Return all automations created by Styx in this session.

        Each entry contains ``automation_id``, ``alias``, ``created_at``,
        ``antecedent``, and ``consequent``.
        """
        with self._lock:
            return list(self._created)

    # ------------------------------------------------------------------
    # Trigger / Action builders
    # ------------------------------------------------------------------

    def _build_trigger(self, antecedent: str) -> list:
        """Parse the antecedent string and return a list of HA trigger dicts.

        Supported patterns:
          - Time-based:  ``"at 18:00"`` / ``"um 06:30"`` / ``"every day at 22:00"``
          - State-based: ``"when <entity> turns on"`` / ``"when <entity> becomes <state>"``
          - Sun-based:   ``"when the sun sets"`` / ``"at sunset"`` / ``"at sunrise"``

        Raises ``ValueError`` if no pattern matches.
        """
        text = antecedent.lower()

        # -- Sun triggers -------------------------------------------------
        if "sunset" in text or "sun sets" in text or "sonnenuntergang" in text:
            return [{"platform": "sun", "event": "sunset"}]
        if "sunrise" in text or "sun rises" in text or "sonnenaufgang" in text:
            return [{"platform": "sun", "event": "sunrise"}]

        # -- Time triggers ------------------------------------------------
        time_match = re.search(
            r'(?:at|um|gegen)\s+(\d{1,2})[:\.](\d{2})', text,
        )
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            return [{"platform": "time", "at": f"{hour:02d}:{minute:02d}:00"}]

        # -- State triggers -----------------------------------------------
        # Pattern: "when <entity_id> turns on/off"
        state_match = re.search(
            r'when\s+([\w.]+)\s+(?:turns?\s+|becomes?\s+|is\s+)(\w+)', text,
        )
        if state_match:
            entity_id = state_match.group(1)
            to_state = state_match.group(2)
            return [{"platform": "state", "entity_id": entity_id, "to": to_state}]

        # Pattern (DE): "wenn <entity_id> auf <state> wechselt"
        state_match_de = re.search(
            r'wenn\s+([\w.]+)\s+auf\s+(\w+)\s+wechselt', text,
        )
        if state_match_de:
            entity_id = state_match_de.group(1)
            to_state = state_match_de.group(2)
            return [{"platform": "state", "entity_id": entity_id, "to": to_state}]

        raise ValueError(
            f"Could not determine trigger type from: {antecedent!r}"
        )

    def _build_action(self, consequent: str) -> list:
        """Parse the consequent string and return a list of HA action dicts.

        Supported patterns:
          - Service call: ``"turn on <entity>"`` / ``"turn off <entity>"``
          - Scene:        ``"activate scene.<name>"``
          - Notification: ``"notify <message>"``

        Raises ``ValueError`` if no pattern matches.
        """
        text = consequent.lower()

        # -- Turn on / off ------------------------------------------------
        on_match = re.search(
            r'turn\s+on\s+([\w.]+)', text,
        )
        if on_match:
            entity_id = on_match.group(1)
            domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"
            return [{
                "service": f"{domain}.turn_on",
                "target": {"entity_id": entity_id},
            }]

        off_match = re.search(
            r'turn\s+off\s+([\w.]+)', text,
        )
        if off_match:
            entity_id = off_match.group(1)
            domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"
            return [{
                "service": f"{domain}.turn_off",
                "target": {"entity_id": entity_id},
            }]

        # -- German: einschalten / ausschalten ----------------------------
        ein_match = re.search(
            r'([\w.]+)\s+einschalten', text,
        )
        if ein_match:
            entity_id = ein_match.group(1)
            domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"
            return [{
                "service": f"{domain}.turn_on",
                "target": {"entity_id": entity_id},
            }]

        aus_match = re.search(
            r'([\w.]+)\s+ausschalten', text,
        )
        if aus_match:
            entity_id = aus_match.group(1)
            domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"
            return [{
                "service": f"{domain}.turn_off",
                "target": {"entity_id": entity_id},
            }]

        # -- Activate scene -----------------------------------------------
        scene_match = re.search(r'(?:activate|scene)\s+(scene\.[\w]+)', text)
        if scene_match:
            return [{
                "service": "scene.turn_on",
                "target": {"entity_id": scene_match.group(1)},
            }]

        # -- Notification -------------------------------------------------
        notify_match = re.search(r'notify\s+(.+)', text)
        if notify_match:
            message = notify_match.group(1).strip()
            return [{
                "service": "notify.persistent_notification",
                "data": {"message": message, "title": "PilotSuite"},
            }]

        raise ValueError(
            f"Could not determine action from: {consequent!r}"
        )
