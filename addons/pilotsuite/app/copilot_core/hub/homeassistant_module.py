"""HomeAssistant Integration Module — HA-Frontend-Status und Event-Forwarding (v1.1.0).

Verwaltet Konfiguration und Status der HA-Integration (pilotsuite-styx-ha).
Trackt Verbindungsstatus, Event-Forwarding, Webhook-Pushes, Dashboard-Views
und Supervisor-API-Zustand.

Features:
- Verbindungsstatus mit Response-Time-Tracking
- Event-Forwarding-Konfiguration pro Domain
- Webhook-Push-Statistik
- Bidirektionale Webhook-Empfangs-Statistik (HA -> Core)
- Connection Diagnostics (Uptime, Error-Tracking)
- Pipeline Health mit Status-Farben
- Dashboard-View-Tracking
- Supervisor-API-Health
- LLM-Kontext fuer Sprachsteuerung mit Verbindungsqualitaet
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

        # Bidirektionale Diagnostics
        self._connected_at: float = time.monotonic()
        self._last_webhook_received_at: datetime | None = None
        self._webhook_received_count: int = 0
        self._webhook_event_types: dict[str, int] = {}
        self._last_event_forwarded_at: datetime | None = None
        self._last_error: str | None = None

        self._config: dict[str, Any] = {
            "enabled": True,
            "forwarded_domains": [
                "light", "sensor", "binary_sensor", "switch",
                "climate", "media_player", "cover", "fan",
            ],
            "webhook_retry_count": 3,
            "connection_timeout_s": 10,
        }

    # -- Connection ----------------------------------------------------------

    def update_connection_status(
        self, reachable: bool, response_time_ms: float,
        error_message: str = "",
    ) -> None:
        """Aktualisiert den Verbindungsstatus zur HA-Instanz."""
        now = datetime.now(tz=timezone.utc)
        self._connection.reachable = reachable
        self._connection.response_time_ms = response_time_ms
        if reachable:
            self._connection.last_successful_call = now
            self._connection.success_count += 1
            # Verbindung wiederhergestellt — Uptime-Timer neu starten
            if self._connection.error_count > 0 and not error_message:
                self._connected_at = time.monotonic()
        else:
            self._connection.last_failed_call = now
            self._connection.error_count += 1
            if error_message:
                self._last_error = error_message
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

    def record_event_forwarded(self, domain: str, count: int = 1) -> None:
        """Zeichnet weitergeleitete Events auf.

        Args:
            domain: HA-Domain des Events (z.B. "light", "sensor")
            count: Anzahl der Events im Batch (Default: 1)
        """
        now_mono = time.monotonic()
        now_utc = datetime.now(tz=timezone.utc)
        self._event_forwarding.events_forwarded_count += count
        self._event_forwarding.last_event_at = now_utc
        self._last_event_forwarded_at = now_utc

        # Domain-Zaehler
        if domain not in self._event_forwarding.domain_counts:
            self._event_forwarding.domain_counts[domain] = 0
        self._event_forwarding.domain_counts[domain] += count

        # Events-per-minute Berechnung (gleitendes 60-Sekunden-Fenster)
        for _ in range(count):
            self._event_timestamps.append(now_mono)
        cutoff = now_mono - 60.0
        self._event_timestamps = [t for t in self._event_timestamps if t > cutoff]
        self._event_forwarding.events_per_minute = float(len(self._event_timestamps))

        logger.debug(
            "HA-Modul: %d Event(s) weitergeleitet (Domain: %s, Gesamt: %d, %.1f/min)",
            count,
            domain,
            self._event_forwarding.events_forwarded_count,
            self._event_forwarding.events_per_minute,
        )

    # -- Webhook -------------------------------------------------------------

    def record_webhook_push(self, success: bool, error_message: str = "") -> None:
        """Zeichnet einen Webhook-Push (Core -> HA) auf."""
        self._webhook.last_push = datetime.now(tz=timezone.utc)
        self._webhook.push_count += 1
        if not success:
            self._webhook.push_errors += 1
            self._webhook.last_error_message = error_message
            self._last_error = f"Webhook-Push fehlgeschlagen: {error_message}"
        logger.debug(
            "HA-Modul: Webhook-Push %s (Gesamt: %d, Fehler: %d)",
            "erfolgreich" if success else "fehlgeschlagen",
            self._webhook.push_count,
            self._webhook.push_errors,
        )

    def record_webhook(self, event_type: str) -> None:
        """Zeichnet einen empfangenen Webhook (HA -> Core) auf.

        Wird aufgerufen wenn die HA-Integration einen Webhook an Core sendet.

        Args:
            event_type: Typ des Webhook-Events (z.B. "state_changed",
                        "automation_triggered", "heartbeat")
        """
        self._last_webhook_received_at = datetime.now(tz=timezone.utc)
        self._webhook_received_count += 1
        if event_type not in self._webhook_event_types:
            self._webhook_event_types[event_type] = 0
        self._webhook_event_types[event_type] += 1
        logger.debug(
            "HA-Modul: Webhook empfangen (Typ: %s, Gesamt: %d)",
            event_type,
            self._webhook_received_count,
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

    # -- Config ---------------------------------------------------------------

    def get_config(self) -> dict[str, Any]:
        """Gibt aktuelle Modul-Konfiguration zurueck."""
        return dict(self._config)

    def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Aktualisiert Modul-Konfiguration."""
        self._config.update(updates)
        # Sync forwarded_domains wenn geaendert
        if "forwarded_domains" in updates:
            self.configure_forwarded_domains(updates["forwarded_domains"])
        return dict(self._config)

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

    # -- Diagnostics ---------------------------------------------------------

    def get_diagnostics(self) -> dict[str, Any]:
        """Vollstaendige Diagnostik-Informationen fuer Debugging.

        Umfasst Connection-Diagnostics, Pipeline-Metriken, Webhook-Empfang,
        Supervisor-Health und Konfiguration.

        Returns:
            Dict mit allen diagnostischen Informationen
        """
        conn = self._connection
        ef = self._event_forwarding
        wh = self._webhook
        sv = self._supervisor
        uptime_s = round(time.monotonic() - self._connected_at, 1)

        return {
            "connection": {
                "reachable": conn.reachable,
                "last_successful_call": conn.last_successful_call.isoformat() if conn.last_successful_call else None,
                "last_failed_call": conn.last_failed_call.isoformat() if conn.last_failed_call else None,
                "response_time_ms": conn.response_time_ms,
                "error_count": conn.error_count,
                "success_count": conn.success_count,
                "connection_uptime_s": uptime_s,
            },
            "webhook_inbound": {
                "last_webhook_received_at": self._last_webhook_received_at.isoformat() if self._last_webhook_received_at else None,
                "webhook_received_count": self._webhook_received_count,
                "event_types": dict(self._webhook_event_types),
            },
            "webhook_outbound": {
                "last_push": wh.last_push.isoformat() if wh.last_push else None,
                "push_count": wh.push_count,
                "push_errors": wh.push_errors,
                "last_error_message": wh.last_error_message,
            },
            "event_forwarding": {
                "forwarded_domains": ef.forwarded_domains,
                "entities_tracked": len(ef.domain_counts),
                "events_forwarded_count": ef.events_forwarded_count,
                "events_per_minute": round(ef.events_per_minute, 1),
                "domain_counts": dict(ef.domain_counts),
                "last_event_at": ef.last_event_at.isoformat() if ef.last_event_at else None,
                "last_event_forwarded_at": self._last_event_forwarded_at.isoformat() if self._last_event_forwarded_at else None,
            },
            "supervisor": {
                "reachable": sv.reachable,
                "token_valid": sv.token_valid,
                "last_check": sv.last_check.isoformat() if sv.last_check else None,
            },
            "pipeline": {
                "integration_entity_count": self._integration_entity_count,
                "module_count": self._module_count,
                "active_dashboard_views": list(self._active_dashboard_views),
                "last_error": self._last_error,
            },
            "config": dict(self._config),
        }

    def get_pipeline_health(self) -> dict[str, Any]:
        """Pipeline-Health-Summary mit Status-Farben.

        Bewertet die Gesamtgesundheit der HA-Core-Pipeline anhand von
        Verbindungsstatus, Webhook-Aktivitaet und Fehlerquote.

        Returns:
            Dict mit status, color, und Detail-Checks
        """
        conn = self._connection
        wh = self._webhook
        ef = self._event_forwarding
        sv = self._supervisor

        checks: dict[str, dict[str, Any]] = {}

        # 1. Connection Check
        if conn.reachable:
            checks["connection"] = {"status": "ok", "color": "green", "detail": f"{conn.response_time_ms:.0f} ms"}
        else:
            checks["connection"] = {"status": "error", "color": "red", "detail": "nicht erreichbar"}

        # 2. Webhook Inbound Check (HA -> Core)
        if self._webhook_received_count > 0 and self._last_webhook_received_at:
            age_s = (datetime.now(tz=timezone.utc) - self._last_webhook_received_at).total_seconds()
            if age_s < 300:  # 5 Minuten
                checks["webhook_inbound"] = {"status": "ok", "color": "green", "detail": f"{self._webhook_received_count} empfangen"}
            else:
                checks["webhook_inbound"] = {"status": "warning", "color": "yellow", "detail": f"letzter vor {age_s:.0f}s"}
        else:
            checks["webhook_inbound"] = {"status": "inactive", "color": "gray", "detail": "keine Webhooks empfangen"}

        # 3. Webhook Outbound Check (Core -> HA)
        if wh.push_count > 0:
            error_rate = wh.push_errors / wh.push_count if wh.push_count > 0 else 0.0
            if error_rate < 0.05:
                checks["webhook_outbound"] = {"status": "ok", "color": "green", "detail": f"{wh.push_count} gesendet"}
            elif error_rate < 0.2:
                checks["webhook_outbound"] = {"status": "warning", "color": "yellow", "detail": f"{wh.push_errors}/{wh.push_count} Fehler"}
            else:
                checks["webhook_outbound"] = {"status": "error", "color": "red", "detail": f"{wh.push_errors}/{wh.push_count} Fehler"}
        else:
            checks["webhook_outbound"] = {"status": "inactive", "color": "gray", "detail": "keine Pushes"}

        # 4. Event Forwarding Check
        if ef.events_forwarded_count > 0:
            if ef.events_per_minute > 0:
                checks["event_forwarding"] = {"status": "ok", "color": "green", "detail": f"{ef.events_per_minute:.0f}/min"}
            else:
                checks["event_forwarding"] = {"status": "warning", "color": "yellow", "detail": "keine aktiven Events"}
        else:
            checks["event_forwarding"] = {"status": "inactive", "color": "gray", "detail": "kein Forwarding"}

        # 5. Supervisor Check
        if sv.reachable and sv.token_valid:
            checks["supervisor"] = {"status": "ok", "color": "green", "detail": "erreichbar, Token gueltig"}
        elif sv.reachable:
            checks["supervisor"] = {"status": "warning", "color": "yellow", "detail": "erreichbar, Token ungueltig"}
        else:
            checks["supervisor"] = {"status": "error", "color": "red", "detail": "nicht erreichbar"}

        # Gesamtstatus ableiten
        colors = [c["color"] for c in checks.values()]
        if "red" in colors:
            overall_status = "unhealthy"
            overall_color = "red"
        elif "yellow" in colors:
            overall_status = "degraded"
            overall_color = "yellow"
        elif all(c == "gray" for c in colors):
            overall_status = "initializing"
            overall_color = "gray"
        else:
            overall_status = "healthy"
            overall_color = "green"

        return {
            "status": overall_status,
            "color": overall_color,
            "uptime_s": round(time.monotonic() - self._connected_at, 1),
            "last_error": self._last_error,
            "checks": checks,
        }

    # -- Summary / LLM -------------------------------------------------------

    def get_summary(self) -> dict[str, Any]:
        """Zusammenfassung fuer API-Antworten — inkl. bidirektionaler Metriken."""
        d = self.get_status()
        health = self.get_pipeline_health()
        uptime_s = round(time.monotonic() - self._connected_at, 1)

        return {
            "connection": d.connection,
            "event_forwarding": d.event_forwarding,
            "webhook": d.webhook,
            "supervisor": d.supervisor,
            "integration_entity_count": d.integration_entity_count,
            "module_count": d.module_count,
            "active_dashboard_views": d.active_dashboard_views,
            # Bidirektionale Metriken
            "webhook_inbound": {
                "last_webhook_received_at": self._last_webhook_received_at.isoformat() if self._last_webhook_received_at else None,
                "webhook_received_count": self._webhook_received_count,
                "event_types": dict(self._webhook_event_types),
            },
            "diagnostics": {
                "connection_uptime_s": uptime_s,
                "entities_tracked": len(self._event_forwarding.domain_counts),
                "events_per_minute": round(self._event_forwarding.events_per_minute, 1),
                "last_event_forwarded_at": self._last_event_forwarded_at.isoformat() if self._last_event_forwarded_at else None,
                "last_error": self._last_error,
            },
            "pipeline_health": {
                "status": health["status"],
                "color": health["color"],
            },
        }

    def get_context_for_llm(self) -> str:
        """LLM-Kontextinjektion mit Verbindungsqualitaet."""
        conn = self._connection
        ef = self._event_forwarding
        wh = self._webhook
        sv = self._supervisor
        health = self.get_pipeline_health()
        uptime_s = round(time.monotonic() - self._connected_at, 1)

        conn_status = "verbunden" if conn.reachable else "getrennt"
        sv_status = "ok" if sv.reachable and sv.token_valid else "Problem"

        # Verbindungsqualitaet berechnen
        total_calls = conn.success_count + conn.error_count
        if total_calls > 0:
            success_rate = conn.success_count / total_calls * 100
            quality = f"{success_rate:.0f}% Erfolgsrate"
        else:
            quality = "keine Daten"

        lines = [
            f"HA-Integration: {conn_status} "
            f"({conn.response_time_ms:.0f} ms, {conn.error_count} Fehler)",
            f"  Verbindungsqualitaet: {quality}, Uptime: {uptime_s:.0f}s",
            f"  Pipeline: {health['status']}",
        ]

        if ef.forwarded_domains:
            lines.append(
                f"  Event-Forwarding: {ef.events_forwarded_count} Events "
                f"({ef.events_per_minute:.0f}/min), "
                f"Domains: {', '.join(ef.forwarded_domains)}"
            )

        lines.append(
            f"  Webhooks: {wh.push_count} gesendet, {self._webhook_received_count} empfangen, "
            f"{wh.push_errors} Fehler"
        )
        lines.append(
            f"  Entities: {self._integration_entity_count}, "
            f"Module: {self._module_count}, "
            f"Views: {len(self._active_dashboard_views)}"
        )
        lines.append(f"  Supervisor-API: {sv_status}")

        if self._last_error:
            lines.append(f"  Letzter Fehler: {self._last_error}")

        return "\n".join(lines)
