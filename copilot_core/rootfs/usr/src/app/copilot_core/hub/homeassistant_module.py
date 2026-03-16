"""HomeAssistant Integration Module — HA-Frontend-Status und Event-Forwarding (v1.0.0).

Verwaltet Konfiguration und Status der HA-Integration (pilotsuite-styx-ha).
Trackt Verbindungsstatus, Event-Forwarding, Webhook-Pushes, Dashboard-Views
und Supervisor-API-Zustand.

Features:
- Verbindungsstatus mit Response-Time-Tracking
- Event-Forwarding-Konfiguration pro Domain
- Webhook-Push-Statistik
- Dashboard-View-Tracking
- Supervisor-API-Health
- LLM-Kontext fuer Sprachsteuerung
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConnectionStatus:
    """Verbindungszustand zur HA-Instanz."""

    reachable: bool = False
    last_successful_call: datetime | None = None
    last_failed_call: datetime | None = None
    response_time_ms: float = 0.0
    error_count: int = 0
    success_count: int = 0


@dataclass
class EventForwardingConfig:
    """Konfiguration und Statistik des Event-Forwardings."""

    forwarded_domains: list[str] = field(default_factory=list)
    events_forwarded_count: int = 0
    events_per_minute: float = 0.0
    domain_counts: dict[str, int] = field(default_factory=dict)
    last_event_at: datetime | None = None


@dataclass
class WebhookStatus:
    """Status der Webhook-Pushes (Core -> HA)."""

    last_push: datetime | None = None
    push_count: int = 0
    push_errors: int = 0
    last_error_message: str = ""


@dataclass
class SupervisorHealth:
    """Zustand der Supervisor-API-Verbindung."""

    reachable: bool = False
    token_valid: bool = False
    last_check: datetime | None = None


@dataclass
class HomeAssistantDashboard:
    """Komplettes HomeAssistant-Modul-Dashboard."""

    connection: dict[str, Any] = field(default_factory=dict)
    event_forwarding: dict[str, Any] = field(default_factory=dict)
    webhook: dict[str, Any] = field(default_factory=dict)
    supervisor: dict[str, Any] = field(default_factory=dict)
    integration_entity_count: int = 0
    module_count: int = 0
    active_dashboard_views: list[str] = field(default_factory=list)


class HomeAssistantModuleEngine:
    """HomeAssistant Integration Module Engine — verwaltet HA-Frontend-Status."""

    def __init__(self) -> None:
        self._connection = ConnectionStatus()
        self._event_forwarding = EventForwardingConfig()
        self._webhook = WebhookStatus()
        self._supervisor = SupervisorHealth()
        self._integration_entity_count: int = 0
        self._module_count: int = 0
        self._active_dashboard_views: list[str] = []
        self._event_timestamps: list[float] = []

    # -- Connection ----------------------------------------------------------

    def update_connection_status(
        self, reachable: bool, response_time_ms: float,
    ) -> None:
        """Aktualisiert den Verbindungsstatus zur HA-Instanz."""
        now = datetime.now(tz=timezone.utc)
        self._connection.reachable = reachable
        self._connection.response_time_ms = response_time_ms
        if reachable:
            self._connection.last_successful_call = now
            self._connection.success_count += 1
        else:
            self._connection.last_failed_call = now
            self._connection.error_count += 1
        logger.debug(
            "HA-Modul: Verbindung %s (%.1f ms, Fehler: %d)",
            "erreichbar" if reachable else "nicht erreichbar",
            response_time_ms,
            self._connection.error_count,
        )

    # -- Event Forwarding ----------------------------------------------------

    def configure_forwarded_domains(self, domains: list[str]) -> None:
        """Konfiguriert welche Domains weitergeleitet werden."""
        self._event_forwarding.forwarded_domains = list(domains)
        logger.debug("HA-Modul: Event-Forwarding konfiguriert fuer %d Domains", len(domains))

    def record_event_forwarded(self, domain: str) -> None:
        """Zeichnet ein weitergeleitetes Event auf."""
        now_mono = time.monotonic()
        self._event_forwarding.events_forwarded_count += 1
        self._event_forwarding.last_event_at = datetime.now(tz=timezone.utc)

        # Domain-Zaehler
        if domain not in self._event_forwarding.domain_counts:
            self._event_forwarding.domain_counts[domain] = 0
        self._event_forwarding.domain_counts[domain] += 1

        # Events-per-minute Berechnung (gleitendes 60-Sekunden-Fenster)
        self._event_timestamps.append(now_mono)
        cutoff = now_mono - 60.0
        self._event_timestamps = [t for t in self._event_timestamps if t > cutoff]
        self._event_forwarding.events_per_minute = float(len(self._event_timestamps))

        logger.debug(
            "HA-Modul: Event weitergeleitet (Domain: %s, Gesamt: %d, %.1f/min)",
            domain,
            self._event_forwarding.events_forwarded_count,
            self._event_forwarding.events_per_minute,
        )

    # -- Webhook -------------------------------------------------------------

    def record_webhook_push(self, success: bool, error_message: str = "") -> None:
        """Zeichnet einen Webhook-Push auf."""
        self._webhook.last_push = datetime.now(tz=timezone.utc)
        self._webhook.push_count += 1
        if not success:
            self._webhook.push_errors += 1
            self._webhook.last_error_message = error_message
        logger.debug(
            "HA-Modul: Webhook-Push %s (Gesamt: %d, Fehler: %d)",
            "erfolgreich" if success else "fehlgeschlagen",
            self._webhook.push_count,
            self._webhook.push_errors,
        )

    # -- Integration Metadata ------------------------------------------------

    def set_integration_entity_count(self, count: int) -> None:
        """Setzt die Anzahl der verwalteten Entities."""
        self._integration_entity_count = count

    def set_module_count(self, count: int) -> None:
        """Setzt die Anzahl der geladenen HA-Module."""
        self._module_count = count

    def set_active_dashboard_views(self, views: list[str]) -> None:
        """Setzt die aktiven Dashboard-Views."""
        self._active_dashboard_views = list(views)

    # -- Supervisor ----------------------------------------------------------

    def update_supervisor_health(
        self, reachable: bool, token_valid: bool,
    ) -> None:
        """Aktualisiert den Supervisor-API-Zustand."""
        self._supervisor.reachable = reachable
        self._supervisor.token_valid = token_valid
        self._supervisor.last_check = datetime.now(tz=timezone.utc)
        logger.debug(
            "HA-Modul: Supervisor %s, Token %s",
            "erreichbar" if reachable else "nicht erreichbar",
            "gueltig" if token_valid else "ungueltig",
        )

    # -- Dashboard / Summary / LLM ------------------------------------------

    def get_status(self) -> HomeAssistantDashboard:
        """Erstellt das komplette HomeAssistant-Modul-Dashboard."""
        conn = self._connection
        ef = self._event_forwarding
        wh = self._webhook
        sv = self._supervisor

        return HomeAssistantDashboard(
            connection={
                "reachable": conn.reachable,
                "last_successful_call": conn.last_successful_call.isoformat() if conn.last_successful_call else None,
                "last_failed_call": conn.last_failed_call.isoformat() if conn.last_failed_call else None,
                "response_time_ms": conn.response_time_ms,
                "error_count": conn.error_count,
                "success_count": conn.success_count,
            },
            event_forwarding={
                "forwarded_domains": ef.forwarded_domains,
                "events_forwarded_count": ef.events_forwarded_count,
                "events_per_minute": round(ef.events_per_minute, 1),
                "domain_counts": dict(ef.domain_counts),
                "last_event_at": ef.last_event_at.isoformat() if ef.last_event_at else None,
            },
            webhook={
                "last_push": wh.last_push.isoformat() if wh.last_push else None,
                "push_count": wh.push_count,
                "push_errors": wh.push_errors,
                "last_error_message": wh.last_error_message,
            },
            supervisor={
                "reachable": sv.reachable,
                "token_valid": sv.token_valid,
                "last_check": sv.last_check.isoformat() if sv.last_check else None,
            },
            integration_entity_count=self._integration_entity_count,
            module_count=self._module_count,
            active_dashboard_views=list(self._active_dashboard_views),
        )

    def get_summary(self) -> dict[str, Any]:
        """Zusammenfassung fuer API-Antworten."""
        d = self.get_status()
        return {
            "connection": d.connection,
            "event_forwarding": d.event_forwarding,
            "webhook": d.webhook,
            "supervisor": d.supervisor,
            "integration_entity_count": d.integration_entity_count,
            "module_count": d.module_count,
            "active_dashboard_views": d.active_dashboard_views,
        }

    def get_context_for_llm(self) -> str:
        """LLM-Kontextinjektion."""
        conn = self._connection
        ef = self._event_forwarding
        wh = self._webhook
        sv = self._supervisor

        conn_status = "verbunden" if conn.reachable else "getrennt"
        sv_status = "ok" if sv.reachable and sv.token_valid else "Problem"

        lines = [
            f"HA-Integration: {conn_status} "
            f"({conn.response_time_ms:.0f} ms, {conn.error_count} Fehler)",
        ]

        if ef.forwarded_domains:
            lines.append(
                f"  Event-Forwarding: {ef.events_forwarded_count} Events "
                f"({ef.events_per_minute:.0f}/min), "
                f"Domains: {', '.join(ef.forwarded_domains)}"
            )

        lines.append(
            f"  Webhooks: {wh.push_count} Pushes, {wh.push_errors} Fehler"
        )
        lines.append(
            f"  Entities: {self._integration_entity_count}, "
            f"Module: {self._module_count}, "
            f"Views: {len(self._active_dashboard_views)}"
        )
        lines.append(f"  Supervisor-API: {sv_status}")

        return "\n".join(lines)
