"""Webhook Pusher -- Ereignisse an den HACS-Integrations-Webhook senden.

Sendet typisierte Umschlag-Payloads (Envelope) an den HA-Webhooks-Endpunkt.
Die Zustellung laeuft ueber eine zentrale DeliveryQueue mit festem Worker-Pool,
sodass kein Thread-pro-Event Muster mehr entsteht.

Envelope-Format (muss mit dem webhook.py-Handler uebereinstimmen)::

    {"type": "<event_type>", "data": {<payload>}}

Kanonische event_type-Werte: "status", "mood", "neuron", "suggestion",
"neuron_fired", "brain_insight", "candidates_ranked", "zone_mood".
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from copilot_core.habitat.homeassistant_adapter import normalize_outbound_payload
from copilot_core.webhook_delivery import WebhookDeliveryQueue
from copilot_core.webhook_destination_policy import (
    default_webhook_destination_policy_from_env,
)
from copilot_core.webhook_signing import build_webhook_signature

_LOGGER = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


EVENT_TYPE_STATUS = "status"
EVENT_TYPE_MOOD = "mood"
EVENT_TYPE_NEURON = "neuron"
EVENT_TYPE_SUGGESTION = "suggestion"
EVENT_TYPE_ANOMALY = "anomaly"
EVENT_TYPE_NEURON_FIRED = "neuron_fired"
EVENT_TYPE_BRAIN_INSIGHT = "brain_insight"
EVENT_TYPE_CANDIDATES_RANKED = "candidates_ranked"
EVENT_TYPE_ZONE_MOOD = "zone_mood"


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
        destination_max_concurrency: Optional[int] = None,
        destination_rate_limit_per_second: Optional[float] = None,
        destination_rate_limit_burst: int = 1,
        destination_policy: Optional[Callable[[str], bool]] = None,
        webhook_signing_secret: str = "",  # legacy alias for *_primary
        webhook_signing_secret_primary: str = "",
        webhook_signing_secret_secondary: str = "",
        webhook_signing_timestamp_ttl_seconds: int = 300,
    ) -> None:
        self._url = webhook_url
        self._token = webhook_token
        # Pusher ist nur aktiv, wenn eine webhook_url konfiguriert wurde
        self._enabled = bool(webhook_url)
        self._delivery_queue: Optional[WebhookDeliveryQueue] = None
        self._destination_policy = destination_policy

        # Signing key rotation:
        # - legacy `webhook_signing_secret` is an alias for `*_primary`
        # - sender always signs with primary
        # - receiver should verify with (primary, secondary)
        legacy_secret = webhook_signing_secret or ""
        primary_secret = webhook_signing_secret_primary or legacy_secret
        secondary_secret = webhook_signing_secret_secondary or ""

        if (
            webhook_signing_secret_primary
            and legacy_secret
            and webhook_signing_secret_primary != legacy_secret
        ):
            raise ValueError(
                "webhook_signing_secret is a legacy alias; do not set it together with webhook_signing_secret_primary"
            )
        if secondary_secret and not primary_secret:
            raise ValueError(
                "webhook_signing_secret_primary must be set when webhook_signing_secret_secondary is set"
            )

        self._signing_secret_primary = primary_secret
        self._signing_secret_secondary = secondary_secret

        if self._signing_secret_primary:
            try:
                ttl_seconds = int(webhook_signing_timestamp_ttl_seconds)
            except (TypeError, ValueError) as exc:  # noqa: BLE001
                raise ValueError(
                    "webhook_signing_timestamp_ttl_seconds must be a positive int"
                ) from exc
            if ttl_seconds <= 0:
                raise ValueError("webhook_signing_timestamp_ttl_seconds must be > 0")
            self._signing_timestamp_ttl_seconds = ttl_seconds
        else:
            self._signing_timestamp_ttl_seconds = 0

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
                destination_max_concurrency=destination_max_concurrency,
                destination_rate_limit_per_second=destination_rate_limit_per_second,
                destination_rate_limit_burst=destination_rate_limit_burst,
            )

    @property
    def enabled(self) -> bool:
        """Gibt True zurueck, wenn eine Webhook-URL konfiguriert ist und der Pusher aktiv ist."""
        return self._enabled

    # ------------------------------------------------------------------
    # Public push methods
    # ------------------------------------------------------------------

    def push_mood_changed(
        self,
        mood: str,
        confidence: float,
        zone_moods: Optional[Dict[str, Any]] = None,
        top_neurons: Optional[List[Dict[str, Any]]] = None,
        mood_dimensions: Optional[Dict[str, float]] = None,
    ) -> None:
        """Sendet ein mood-Ereignis mit Stimmung, Konfidenz und optionalen Anreicherungen.

        Args:
            mood: Dominante Stimmung (z.B. "relax", "focus").
            confidence: Konfidenzwert [0, 1].
            zone_moods: Per-zone mood data (zone_id -> {comfort, joy, frugality}).
            top_neurons: Top 3 most active neurons [{id, layer, value}].
            mood_dimensions: Mood dimension scores {comfort, joy, frugality}.
        """
        data: Dict[str, Any] = {
            "mood": mood,
            "confidence": round(confidence, 4),
        }
        if zone_moods:
            data["zone_moods"] = zone_moods
        if top_neurons:
            data["top_neurons"] = top_neurons[:3]
        if mood_dimensions:
            data["mood_dimensions"] = {
                k: round(v, 3) for k, v in mood_dimensions.items()
            }
        self._send_envelope(EVENT_TYPE_MOOD, data)

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
                # PS-HEPH-023
                "rate_limited_total": 0,
                "destination_concurrency_wait_total": 0,
                "destination_concurrency_timeout_total": 0,
                # Pusher-only
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

    def push_module_data(self, modules: Dict[str, Any]) -> None:
        """Sendet ein module_data-Ereignis mit allen 5 Modul-Summaries an HA.

        Wird nach jeder Modul-Evaluation aufgerufen, damit die HA-Integration
        Echtzeit-Updates erhaelt (statt nur 120s Polling).

        Args:
            modules: Dict mit Modul-Summaries {licht: {...}, heiz: {...}, ...}
        """
        self._send_envelope("module_data", {"modules": modules})

    def push_anomaly_detected(self, anomaly_data: Dict[str, Any]) -> bool:
        """Sendet ein anomaly-Ereignis an die HACS-Integration.

        Args:
            anomaly_data: Anomaly detection result with entity_id, severity, score, etc.

        Returns:
            True if the envelope was accepted, False if validation failed.
        """
        required = ("entity_id", "anomaly_type", "severity")
        if not all(k in anomaly_data for k in required):
            _LOGGER.warning(
                "Anomaly push skipped: missing required fields %s",
                [k for k in required if k not in anomaly_data],
            )
            return False
        # Trim description if oversized (keep well below payload limit)
        for desc_key in ("description", "description_de", "description_en"):
            desc = anomaly_data.get(desc_key, "")
            if isinstance(desc, str) and len(desc) > 500:
                anomaly_data[desc_key] = desc[:497] + "..."
        self._send_envelope(EVENT_TYPE_ANOMALY, anomaly_data)
        return True

    def push_zone_update(self, zone_id: str, zone_data: Dict[str, Any]) -> None:
        """Sendet ein zone_update-Ereignis fuer eine einzelne Zone.

        Args:
            zone_id: Zone identifier
            zone_data: Per-zone data from all modules
        """
        self._send_envelope("zone_update", {
            "zone_id": zone_id,
            **zone_data,
        })

    def push_neuron_fired(
        self, neuron_id: str, layer: str, value: float, confidence: float,
    ) -> None:
        """Push when a significant neuron fires (value crosses threshold)."""
        self._send_envelope(EVENT_TYPE_NEURON_FIRED, {
            "neuron_id": neuron_id,
            "layer": layer,
            "value": round(value, 3),
            "confidence": round(confidence, 3),
            "timestamp": _now_iso(),
        })

    def push_brain_insight(self, insight_type: str, data: Dict[str, Any]) -> None:
        """Push brain graph insights (new correlation, pattern, anomaly link).

        Args:
            insight_type: One of "correlation", "sequence", "cluster".
            data: Insight-specific payload (kept compact).
        """
        self._send_envelope(EVENT_TYPE_BRAIN_INSIGHT, {
            "insight_type": insight_type,
            **data,
            "timestamp": _now_iso(),
        })

    def push_candidate_ranked(self, candidates: List[Dict[str, Any]]) -> None:
        """Push top-ranked candidates with scores and explanations."""
        self._send_envelope(EVENT_TYPE_CANDIDATES_RANKED, {
            "candidates": candidates[:10],
            "timestamp": _now_iso(),
        })

    def push_zone_mood(
        self,
        zone_id: str,
        mood: str,
        brightness_factor: float,
        color_temp: int,
    ) -> None:
        """Push per-zone mood adjustment.

        Args:
            zone_id: Zone identifier.
            mood: Active mood state name (e.g. "relax", "focus").
            brightness_factor: Brightness multiplier [0, 1].
            color_temp: Color temperature in Kelvin.
        """
        self._send_envelope(EVENT_TYPE_ZONE_MOOD, {
            "zone_id": zone_id,
            "mood": mood,
            "brightness_factor": round(brightness_factor, 2),
            "color_temp_k": color_temp,
            "timestamp": _now_iso(),
        })

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

    @staticmethod
    def _build_signature(
        secret: str,
        body: bytes,
        timestamp: str,
        nonce: str,
    ) -> str:
        # Legacy shim (kept for callers/tests): canonical implementation lives in
        # `copilot_core.webhook_signing`.
        return build_webhook_signature(
            secret,
            body=body,
            timestamp=timestamp,
            nonce=nonce,
        )

    def _send_envelope(self, event_type: str, data: Dict[str, Any]) -> None:
        """Umschlag bauen und in die DeliveryQueue enqueuen."""
        if not self._enabled:
            return

        envelope = {"type": event_type, "data": normalize_outbound_payload(event_type, data)}

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

        if self._signing_secret_primary:
            timestamp = str(int(time.time()))
            nonce = uuid.uuid4().hex
            signature = self._build_signature(
                self._signing_secret_primary,
                body=body,
                timestamp=timestamp,
                nonce=nonce,
            )
            req.add_header("X-Webhook-Timestamp", timestamp)
            req.add_header("X-Webhook-Nonce", nonce)
            req.add_header("X-Webhook-Signature", signature)

        try:
            with urllib.request.urlopen(req, timeout=self._request_timeout_seconds) as resp:
                _LOGGER.debug(
                    "Webhook push %s → %d",
                    envelope.get("type"),
                    resp.status,
                )
        except urllib.error.HTTPError as exc:
            _LOGGER.warning(
                "Webhook push %s failed: HTTP %d",
                envelope.get("type"),
                exc.code,
            )
            raise
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Webhook push %s failed: %s", envelope.get("type"), exc)
            raise
