"""Webhook Pusher -- Ereignisse an den HACS-Integrations-Webhook senden.

Sendet typisierte Umschlag-Payloads (Envelope) an den HA-Webhook-Endpunkt.
Die Zustellung laeuft ueber eine zentrale DeliveryQueue mit festem Worker-Pool,
sodass kein Thread-pro-Event Muster mehr entsteht.

Envelope-Format (muss mit dem webhook.py-Handler uebereinstimmen)::

    {"type": "<event_type>", "data": {<payload>}}

Kanonische event_type-Werte: "status", "mood", "neuron", "suggestion".
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Optional

from copilot_core.webhook_delivery import WebhookDeliveryQueue
from copilot_core.webhook_destination_policy import (
    default_webhook_destination_policy_from_env,
)

_LOGGER = logging.getLogger(__name__)


EVENT_TYPE_STATUS = "status"
EVENT_TYPE_MOOD = "mood"
EVENT_TYPE_NEURON = "neuron"
EVENT_TYPE_SUGGESTION = "suggestion"


class WebhookPusher:
    """Nicht-blockierender Webhook-Push-Client (nur stdlib, keine externen Abhaengigkeiten)."""

    def __init__(
        self,
        webhook_url: str,
        webhook_token: str = "",
        worker_count: int = 2,
        max_queue_size: int = 256,
        backpressure_policy: str = "drop_newest",
        block_timeout_seconds: float = 0.1,
        max_payload_bytes: Optional[int] = 65536,
        request_timeout_seconds: float = 10.0,
        delivery_deadline_seconds: Optional[float] = 60.0,
        destination_policy: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self._url = webhook_url
        self._token = webhook_token
        # Pusher ist nur aktiv, wenn eine webhook_url konfiguriert wurde
        self._enabled = bool(webhook_url)
        self._delivery_queue: Optional[WebhookDeliveryQueue] = None
        self._destination_policy = destination_policy
        if self._enabled and self._destination_policy is None:
            # Default SSRF guardrails (configurable via env); can be overridden by callers.
            self._destination_policy = default_webhook_destination_policy_from_env()
        self._parsed_url: Optional[urllib.parse.ParseResult] = None

        if self._enabled:
            self._parsed_url = self._validate_webhook_url(self._url)

            if self._destination_policy is not None:
                try:
                    allowed = bool(self._destination_policy(self._url))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        "destination_policy raised while validating webhook_url"
                    ) from exc

                if not allowed:
                    raise ValueError("webhook_url rejected by destination_policy")

        if max_payload_bytes is not None and max_payload_bytes <= 0:
            raise ValueError("max_payload_bytes must be > 0 or None")
        if request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be > 0")

        self._max_payload_bytes = max_payload_bytes
        self._request_timeout_seconds = request_timeout_seconds
        self._stats_lock = threading.Lock()
        self._payload_oversize_total = 0
        self._destination_rejected_total = 0

        if self._enabled:
            self._delivery_queue = WebhookDeliveryQueue(
                send_func=self._do_post,
                worker_count=worker_count,
                max_queue_size=max_queue_size,
                backpressure_policy=backpressure_policy,
                block_timeout_seconds=block_timeout_seconds,
                delivery_deadline_seconds=delivery_deadline_seconds,
            )

    @property
    def enabled(self) -> bool:
        """Gibt True zurueck, wenn eine Webhook-URL konfiguriert ist und der Pusher aktiv ist."""
        return self._enabled

    # ------------------------------------------------------------------
    # Public push methods
    # ------------------------------------------------------------------

    def push_mood_changed(self, mood: str, confidence: float) -> None:
        """Sendet ein mood-Ereignis mit Stimmung und Konfidenz."""
        self._send_envelope(EVENT_TYPE_MOOD, {
            "mood": mood,
            "confidence": round(confidence, 4),
        })

    def push_neuron_update(self, result_dict: Dict[str, Any]) -> None:
        """Sendet ein neuron-Ereignis mit der Pipeline-Ergebniszusammenfassung."""
        self._send_envelope(EVENT_TYPE_NEURON, result_dict)

    def push_suggestion(self, suggestion: Dict[str, Any]) -> None:
        """Sendet ein suggestion-Ereignis (Vorschlag) an die HACS-Integration."""
        self._send_envelope(EVENT_TYPE_SUGGESTION, suggestion)

    def stop(self, drain_timeout: Optional[float] = 1.0) -> None:
        """Stoppt die DeliveryQueue kontrolliert (idempotent)."""
        if self._delivery_queue is None:
            return
        self._delivery_queue.stop(drain_timeout=drain_timeout)

    def get_stats(self) -> Dict[str, int]:
        """Liefert Delivery-Queue-Metriken fuer Observability/Monitoring."""
        if self._delivery_queue is None:
            return {
                "enqueued_total": 0,
                "dropped_total": 0,
                "delivered_total": 0,
                "failed_total": 0,
                "retry_total": 0,
                "deadline_exceeded_total": 0,
                "payload_oversize_total": 0,
                "destination_rejected_total": 0,
                "queue_size": 0,
                "worker_count": 0,
                "workers_alive": 0,
                "started": 0,
            }

        stats = self._delivery_queue.get_stats()
        with self._stats_lock:
            stats["payload_oversize_total"] = self._payload_oversize_total
            stats["destination_rejected_total"] = self._destination_rejected_total
        return stats

    @property
    def stats(self) -> Dict[str, int]:
        """Kurzform fuer get_stats()."""
        return self.get_stats()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_webhook_url(webhook_url: str) -> urllib.parse.ParseResult:
        """Validiert webhook_url gegen triviale SSRF-/Scheme-Footguns.

        Motivation:
        - ``urllib.request`` kann (je nach Scheme) auch lokale Ressourcen oeffnen
          (z. B. ``file://``). Diese Guardrails verhindern, dass ein falsch
          konfigurierter URL zu einem lokalen File-Read oder zu einem ungewuenschten
          Protokollwechsel fuehrt.

        Diese Funktion ist absichtlich konservativ, aber kompatibel mit typischen
        HA-Webhooks (http/https).
        """
        if "\r" in webhook_url or "\n" in webhook_url:
            raise ValueError("webhook_url must not contain CR/LF")

        parsed = urllib.parse.urlparse(webhook_url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("webhook_url must use http or https")
        if not parsed.netloc:
            raise ValueError("webhook_url must be absolute and include a host")
        if parsed.username or parsed.password:
            raise ValueError("webhook_url must not include credentials")
        if parsed.fragment:
            raise ValueError("webhook_url must not include a fragment")

        return parsed

    def _send_envelope(self, event_type: str, data: Dict[str, Any]) -> None:
        """Umschlag bauen und in die DeliveryQueue enqueuen."""
        if not self._enabled:
            return

        envelope = {"type": event_type, "data": data}

        queue_ref = self._delivery_queue
        if queue_ref is None:
            _LOGGER.warning("Webhook pusher enabled but delivery queue missing")
            return

        if self._max_payload_bytes is not None:
            serialized = json.dumps(envelope, default=str).encode("utf-8")
            if len(serialized) > self._max_payload_bytes:
                with self._stats_lock:
                    self._payload_oversize_total += 1
                _LOGGER.warning(
                    "Webhook envelope oversized for %s (%d bytes > %d); dropped",
                    event_type,
                    len(serialized),
                    self._max_payload_bytes,
                )
                return

        accepted = queue_ref.enqueue(envelope)
        if not accepted:
            _LOGGER.warning("Webhook envelope dropped by backpressure policy: %s", event_type)

    def _do_post(self, envelope: Dict[str, Any]) -> None:
        """Fuehrt den eigentlichen HTTP-POST aus (laeuft im Delivery-Worker)."""
        if self._destination_policy is not None:
            try:
                allowed = bool(self._destination_policy(self._url))
            except Exception as exc:  # noqa: BLE001
                with self._stats_lock:
                    self._destination_rejected_total += 1
                raise ValueError("webhook_url rejected by destination_policy") from exc

            if not allowed:
                with self._stats_lock:
                    self._destination_rejected_total += 1
                raise ValueError("webhook_url rejected by destination_policy")

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
            # Contract: send both headers for compatibility across Core/HA clients.
            req.add_header("X-Auth-Token", self._token)
            req.add_header("Authorization", f"Bearer {self._token}")

        try:
            with urllib.request.urlopen(req, timeout=self._request_timeout_seconds) as resp:
                _LOGGER.debug(
                    "Webhook push %s → %d", envelope.get("type"), resp.status
                )
        except urllib.error.HTTPError as exc:
            _LOGGER.warning(
                "Webhook push %s failed: HTTP %d", envelope.get("type"), exc.code
            )
            raise
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Webhook push %s failed: %s", envelope.get("type"), exc)
            raise
