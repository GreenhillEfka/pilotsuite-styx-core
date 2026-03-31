"""
HA Connection Module Read Model — Canonical Core-side HA connection/preparation layer.

Slice 4: HA Connection Module
Goal: Formalize the Core-side HA module as the semantic input connection/preparation layer,
with explicit transport/pipeline health as first-class diagnostics.

Provides:
  - HAConnectionSnapshotV1: typed connection state, forwarding config, diagnostics
  - HAConnectionReadModel: aggregated HA connection view
  - get_ha_connection_read_model(): public API for dashboard/API consumption
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _now_monotonic() -> float:
    """Return current monotonic time."""
    return time.monotonic()


@dataclass
class ConnectionDiagnosticsV1:
    """Connection diagnostics with uptime and error tracking."""
    reachable: bool = False
    response_time_ms: float = 0.0
    success_count: int = 0
    error_count: int = 0
    last_success: Optional[str] = None
    last_error: Optional[str] = None
    last_error_at: Optional[str] = None
    uptime_since: Optional[str] = None
    uptime_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reachable": self.reachable,
            "response_time_ms": round(self.response_time_ms, 2),
            "success_count": self.success_count,
            "error_count": self.error_count,
            "last_success": self.last_success,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at,
            "uptime_since": self.uptime_since,
            "uptime_seconds": round(self.uptime_seconds, 1),
        }


@dataclass
class EventForwardingStateV1:
    """Event forwarding configuration and statistics."""
    enabled: bool = True
    forwarded_domains: List[str] = field(default_factory=list)
    events_forwarded_count: int = 0
    events_per_minute: float = 0.0
    domain_counts: Dict[str, int] = field(default_factory=dict)
    last_event_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "forwarded_domains": list(self.forwarded_domains),
            "events_forwarded_count": self.events_forwarded_count,
            "events_per_minute": round(self.events_per_minute, 2),
            "domain_counts": dict(self.domain_counts),
            "last_event_at": self.last_event_at,
        }


@dataclass
class WebhookDiagnosticsV1:
    """Webhook push/pull diagnostics."""
    # Core -> HA pushes
    last_push: Optional[str] = None
    push_count: int = 0
    push_errors: int = 0
    last_push_error: Optional[str] = None
    
    # HA -> Core receives
    last_received: Optional[str] = None
    received_count: int = 0
    received_by_type: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outbound": {
                "last_push": self.last_push,
                "push_count": self.push_count,
                "push_errors": self.push_errors,
                "last_error": self.last_push_error,
            },
            "inbound": {
                "last_received": self.last_received,
                "received_count": self.received_count,
                "received_by_type": dict(self.received_by_type),
            },
        }


@dataclass
class SupervisorStateV1:
    """Supervisor API connection state."""
    reachable: bool = False
    token_valid: bool = False
    last_check: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reachable": self.reachable,
            "token_valid": self.token_valid,
            "last_check": self.last_check,
        }


@dataclass
class HAConnectionSnapshotV1:
    """
    Canonical HA Connection Module snapshot — the Core truth record.

    This is the formalized connection-module contract:
    - Connection diagnostics (reachability, response time, uptime)
    - Event forwarding config and stats
    - Webhook push/pull diagnostics
    - Supervisor API health
    - Pipeline health status
    """
    module_id: str = "homeassistant"
    module_name_de: str = "Home Assistant Verbindung"
    module_icon: str = "mdi:home-assistant"
    module_color: str = "#03A9F4"
    
    # Connection state
    connection: ConnectionDiagnosticsV1 = field(default_factory=ConnectionDiagnosticsV1)
    
    # Event forwarding
    event_forwarding: EventForwardingStateV1 = field(default_factory=EventForwardingStateV1)
    
    # Webhook diagnostics
    webhook: WebhookDiagnosticsV1 = field(default_factory=WebhookDiagnosticsV1)
    
    # Supervisor
    supervisor: SupervisorStateV1 = field(default_factory=SupervisorStateV1)
    
    # Pipeline health
    pipeline_health: str = "ok"  # ok | degraded | error
    pipeline_health_message: str = ""
    pipeline_color: str = "#34d399"  # green | amber | red
    
    # Integration metadata
    integration_entity_count: int = 0
    module_count: int = 0
    active_dashboard_views: List[str] = field(default_factory=list)
    
    # Freshness
    last_update: str = field(default_factory=_now_iso)
    revision: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "module_name_de": self.module_name_de,
            "module_icon": self.module_icon,
            "module_color": self.module_color,
            "connection": self.connection.to_dict(),
            "event_forwarding": self.event_forwarding.to_dict(),
            "webhook": self.webhook.to_dict(),
            "supervisor": self.supervisor.to_dict(),
            "pipeline_health": self.pipeline_health,
            "pipeline_health_message": self.pipeline_health_message,
            "pipeline_color": self.pipeline_color,
            "integration_entity_count": self.integration_entity_count,
            "module_count": self.module_count,
            "active_dashboard_views": list(self.active_dashboard_views),
            "last_update": self.last_update,
            "revision": self.revision,
        }

    def touch(self) -> None:
        """Update revision and timestamp."""
        self.revision += 1
        self.last_update = _now_iso()

    def compute_pipeline_health(self) -> None:
        """Compute pipeline health status from connection and forwarding state."""
        conn = self.connection
        
        # Error rate computation
        total_ops = conn.success_count + conn.error_count
        error_rate = conn.error_count / max(1, total_ops)
        
        # Determine health status
        if not conn.reachable:
            self.pipeline_health = "error"
            self.pipeline_health_message = "HA nicht erreichbar"
            self.pipeline_color = "#ef4444"  # red
        elif error_rate > 0.1:
            self.pipeline_health = "degraded"
            self.pipeline_health_message = f"Erhöhte Fehlerrate ({error_rate*100:.1f}%)"
            self.pipeline_color = "#f59e0b"  # amber
        elif conn.response_time_ms > 5000:
            self.pipeline_health = "degraded"
            self.pipeline_health_message = f"Lange Antwortzeit ({conn.response_time_ms:.0f}ms)"
            self.pipeline_color = "#f59e0b"  # amber
        else:
            self.pipeline_health = "ok"
            self.pipeline_health_message = "Normalbetrieb"
            self.pipeline_color = "#34d399"  # green
        
        self.touch()


@dataclass
class HAConnectionReadModel:
    """
    Aggregated read model for HA connection module.

    This is the canonical output for dashboard/API consumption.
    """
    generated_at: str = field(default_factory=_now_iso)
    connection: HAConnectionSnapshotV1 = field(default_factory=HAConnectionSnapshotV1)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "connection": self.connection.to_dict(),
            "summary": dict(self.summary),
        }


# ── Internal State ────────────────────────────────────────────────────────────

_ha_connection_state: Dict[str, Any] = {
    "snapshot": None,  # HAConnectionSnapshotV1
    "connected_at": None,  # monotonic timestamp
    "last_revision": 0,
}


# ── Public API ────────────────────────────────────────────────────────────────


def get_ha_connection_read_model(
    ha_module_engine: Any = None,
) -> Dict[str, Any]:
    """
    Build HA Connection Read Model.

    Args:
        ha_module_engine: HomeAssistantModuleEngine instance (optional)

    Returns:
        Dict with connection snapshot and summary
    """
    model = build_ha_connection_read_model(ha_module_engine=ha_module_engine)
    return model.to_dict()


def build_ha_connection_read_model(
    ha_module_engine: Any = None,
) -> HAConnectionReadModel:
    """
    Build HAConnectionReadModel from current services.

    This function can be called directly from api/v1/ endpoints.
    """
    now_str = _now_iso()
    now_mono = _now_monotonic()
    
    snapshot = HAConnectionSnapshotV1()
    
    # ── Load from HA module engine ───────────────────────────────────────
    if ha_module_engine is not None:
        try:
            # Connection status
            conn = ha_module_engine._connection
            snapshot.connection.reachable = conn.reachable
            snapshot.connection.response_time_ms = conn.response_time_ms
            snapshot.connection.success_count = conn.success_count
            snapshot.connection.error_count = conn.error_count
            
            if conn.last_successful_call:
                snapshot.connection.last_success = conn.last_successful_call.isoformat()
            if conn.last_failed_call:
                snapshot.connection.last_error_at = conn.last_failed_call.isoformat()
            
            # Uptime tracking
            if hasattr(ha_module_engine, "_connected_at") and ha_module_engine._connected_at:
                snapshot.connection.uptime_since = datetime.fromtimestamp(
                    ha_module_engine._connected_at, tz=timezone.utc
                ).isoformat()
                snapshot.connection.uptime_seconds = now_mono - ha_module_engine._connected_at
            
            if hasattr(ha_module_engine, "_last_error") and ha_module_engine._last_error:
                snapshot.connection.last_error = ha_module_engine._last_error
            
            # Event forwarding
            fwd = ha_module_engine._event_forwarding
            snapshot.event_forwarding.enabled = ha_module_engine._config.get("enabled", True)
            snapshot.event_forwarding.forwarded_domains = list(fwd.forwarded_domains)
            snapshot.event_forwarding.events_forwarded_count = fwd.events_forwarded_count
            snapshot.event_forwarding.domain_counts = dict(fwd.domain_counts)
            
            if fwd.last_event_at:
                snapshot.event_forwarding.last_event_at = fwd.last_event_at.isoformat()
            
            # Compute events per minute (rough estimate)
            if hasattr(ha_module_engine, "_event_timestamps"):
                timestamps = ha_module_engine._event_timestamps
                if len(timestamps) >= 2:
                    time_span = now_mono - timestamps[0]
                    if time_span > 0:
                        snapshot.event_forwarding.events_per_minute = (len(timestamps) / time_span) * 60
            
            # Webhook diagnostics
            wh = ha_module_engine._webhook
            snapshot.webhook.push_count = wh.push_count
            snapshot.webhook.push_errors = wh.push_errors
            snapshot.webhook.last_push_error = wh.last_error_message
            
            if wh.last_push:
                snapshot.webhook.last_push = wh.last_push.isoformat()
            
            # Inbound webhook tracking
            if hasattr(ha_module_engine, "_last_webhook_received_at") and ha_module_engine._last_webhook_received_at:
                snapshot.webhook.last_received = ha_module_engine._last_webhook_received_at.isoformat()
            if hasattr(ha_module_engine, "_webhook_received_count"):
                snapshot.webhook.received_count = ha_module_engine._webhook_received_count
            if hasattr(ha_module_engine, "_webhook_event_types"):
                snapshot.webhook.received_by_type = dict(ha_module_engine._webhook_event_types)
            
            # Supervisor
            sup = ha_module_engine._supervisor
            snapshot.supervisor.reachable = sup.reachable
            snapshot.supervisor.token_valid = sup.token_valid
            
            if sup.last_check:
                snapshot.supervisor.last_check = sup.last_check.isoformat()
            
            # Integration metadata
            snapshot.integration_entity_count = getattr(ha_module_engine, "_integration_entity_count", 0)
            snapshot.module_count = getattr(ha_module_engine, "_module_count", 0)
            snapshot.active_dashboard_views = getattr(ha_module_engine, "_active_dashboard_views", [])
            
        except Exception:
            _LOGGER.debug("Failed to load HA module engine state", exc_info=True)
    
    # ── Compute pipeline health ─────────────────────────────────────────
    snapshot.compute_pipeline_health()
    
    # ── Build summary ───────────────────────────────────────────────────
    summary = {
        "reachable": snapshot.connection.reachable,
        "pipeline_health": snapshot.pipeline_health,
        "forwarded_domains_count": len(snapshot.event_forwarding.forwarded_domains),
        "events_forwarded": snapshot.event_forwarding.events_forwarded_count,
        "webhook_pushes": snapshot.webhook.push_count,
        "webhook_received": snapshot.webhook.received_count,
        "generated_at": now_str,
        "revision": snapshot.revision,
    }
    
    _ha_connection_state["snapshot"] = snapshot
    _ha_connection_state["last_revision"] = snapshot.revision
    
    return HAConnectionReadModel(
        generated_at=now_str,
        connection=snapshot,
        summary=summary,
    )


def update_ha_connection(
    reachable: bool,
    response_time_ms: float,
    error_message: str = "",
) -> None:
    """
    Update HA connection state.

    Called by HA module engine to report connection status.
    """
    if _ha_connection_state["snapshot"] is None:
        _ha_connection_state["snapshot"] = HAConnectionSnapshotV1()
    
    snapshot = _ha_connection_state["snapshot"]
    snapshot.connection.reachable = reachable
    snapshot.connection.response_time_ms = response_time_ms
    
    if reachable:
        snapshot.connection.success_count += 1
        snapshot.connection.last_success = _now_iso()
    else:
        snapshot.connection.error_count += 1
        snapshot.connection.last_error = error_message
        snapshot.connection.last_error_at = _now_iso()
    
    snapshot.compute_pipeline_health()


def get_ha_connection_state() -> Optional[Dict[str, Any]]:
    """Get current HA connection snapshot."""
    snapshot = _ha_connection_state.get("snapshot")
    if snapshot is None:
        return None
    return snapshot.to_dict()


def reset_ha_connection_state() -> None:
    """Reset HA connection state (for testing)."""
    _ha_connection_state["snapshot"] = None
    _ha_connection_state["connected_at"] = None
    _ha_connection_state["last_revision"] = 0


__all__ = [
    "HAConnectionSnapshotV1",
    "HAConnectionReadModel",
    "ConnectionDiagnosticsV1",
    "EventForwardingStateV1",
    "WebhookDiagnosticsV1",
    "SupervisorStateV1",
    "build_ha_connection_read_model",
    "get_ha_connection_read_model",
    "update_ha_connection",
    "get_ha_connection_state",
    "reset_ha_connection_state",
]
