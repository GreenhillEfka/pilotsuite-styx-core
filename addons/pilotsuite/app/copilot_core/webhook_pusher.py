"""Webhook Pusher -- Ereignisse an den HACS-Integrations-Webhook senden.

Sendet typisierte Umschlag-Payloads (Envelope) an den HA-Webhook-Endpunkt.
Jeder Versand erfolgt in einem Daemon-Thread, damit die Haupt-Pipeline
niemals blockiert wird (nicht-blockierende Zustellung).

Envelope-Format (muss mit dem webhook.py-Handler uebereinstimmen)::

    {"type": "<event_type>", "data": {<payload>}}

Beispiele fuer event_type: "mood_changed", "neuron_update", "suggestion".
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

_LOGGER = logging.getLogger(__name__)


class WebhookPusher:
    """Nicht-blockierender Webhook-Push-Client (nur stdlib, keine externen Abhaengigkeiten).

    Jeder Push wird in einem eigenen Daemon-Thread ausgefuehrt.
    Daemon-Threads werden beim Beenden des Prozesses automatisch gestoppt,
    sodass kein explizites Shutdown noetig ist.
    """

    def __init__(self, webhook_url: str, webhook_token: str = "") -> None:
        self._url = webhook_url
        self._token = webhook_token
        # Pusher ist nur aktiv, wenn eine webhook_url konfiguriert wurde
        self._enabled = bool(webhook_url)

    @property
    def enabled(self) -> bool:
        """Gibt True zurueck, wenn eine Webhook-URL konfiguriert ist und der Pusher aktiv ist."""
        return self._enabled

    # ------------------------------------------------------------------
    # Public push methods
    # ------------------------------------------------------------------

    def push_mood_changed(self, mood: str, confidence: float) -> None:
        """Sendet ein mood_changed-Ereignis mit Stimmung und Konfidenz."""
        self._send_envelope("mood_changed", {
            "mood": mood,
            "confidence": round(confidence, 4),
        })

    def push_neuron_update(self, result_dict: Dict[str, Any]) -> None:
        """Sendet ein neuron_update-Ereignis mit der Pipeline-Ergebniszusammenfassung."""
        self._send_envelope("neuron_update", result_dict)

    def push_suggestion(self, suggestion: Dict[str, Any]) -> None:
        """Sendet ein suggestion-Ereignis (Vorschlag) an die HACS-Integration."""
        self._send_envelope("suggestion", suggestion)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_envelope(self, event_type: str, data: Dict[str, Any]) -> None:
        """Fire-and-Forget POST in einem Daemon-Thread.

        Baut den Umschlag {"type": event_type, "data": data} und startet
        einen Daemon-Thread fuer die HTTP-Zustellung. Der Thread wird nicht
        ueberwacht -- Fehler werden nur geloggt.
        """
        if not self._enabled:
            return

        envelope = {"type": event_type, "data": data}

        t = threading.Thread(
            target=self._do_post,
            args=(envelope,),
            daemon=True,
        )
        t.start()

    def _do_post(self, envelope: Dict[str, Any]) -> None:
        """Fuehrt den eigentlichen HTTP-POST aus (laeuft im Hintergrund-Thread)."""
        body = json.dumps(envelope, default=str).encode("utf-8")

        req = urllib.request.Request(
            self._url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
            },
        )
        if self._token:
            req.add_header("X-CoPilot-Token", self._token)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                _LOGGER.debug(
                    "Webhook push %s → %d", envelope.get("type"), resp.status
                )
        except urllib.error.HTTPError as exc:
            _LOGGER.warning(
                "Webhook push %s failed: HTTP %d", envelope.get("type"), exc.code
            )
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Webhook push %s failed: %s", envelope.get("type"), exc)
