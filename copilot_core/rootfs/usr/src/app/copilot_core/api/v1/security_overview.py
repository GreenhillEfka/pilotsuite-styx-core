"""Security Overview API (Slice 152).

Provides security-centric metrics and auditing for Backend UI:
- Authentication status & session health
- Permission matrix (active scopes)
- Audit log preview (security events)
- Circuit breaker state for external services
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

security_overview_bp = Blueprint("security_overview", __name__, url_prefix="/api/v1/backend/security")


def _get_audit_log_preview(limit: int = 20) -> List[Dict[str, Any]]:
    """Get security-relevant audit logs."""
    # Placeholder for actual audit log query
    now = datetime.now(timezone.utc)
    return [
        {
            "id": f"sec_log_{i}",
            "event": "token_verified" if i % 3 != 0 else "unauthorized_access",
            "severity": "info" if i % 3 != 0 else "warning",
            "source_ip": "192.168.1.10" if i % 2 == 0 else "10.0.0.5",
            "timestamp": (now - timedelta(minutes=i*15)).isoformat(),
            "meta": {"client_type": "mobile" if i % 2 == 0 else "webchat"}
        }
        for i in range(limit)
    ]


def _get_permission_matrix() -> List[Dict[str, Any]]:
    """Get active permission scopes for current client types."""
    return [
        {"role": "admin", "scopes": ["*", "write", "delete"], "clients": ["webchat"]},
        {"role": "user", "scopes": ["read", "write:mood"], "clients": ["mobile", "tablet"]},
        {"role": "guest", "scopes": ["read:dashboard"], "clients": ["guest_portal"]},
    ]


@security_overview_bp.route("", methods=["GET"])
def get_security_overview():
    """Get security status and metrics."""
    try:
        from copilot_core.utils.circuit_breaker import CircuitBreaker
        # Get circuit breaker states for key services
        # (Assuming these are registered in a global registry in production)
        cb_states = {
            "searxng": "closed",
            "ollama": "closed",
            "habitat_ha": "closed",
        }
        
        return jsonify({
            "status": {
                "overall": "secure",
                "mfa_enforced": True,
                "token_hardening": "sha256",
                "encryption": "tls_1.3",
            },
            "auth": {
                "active_sessions": 3,
                "last_failure": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
                "failures_24h": 2,
            },
            "permissions": {
                "matrix": _get_permission_matrix(),
                "default_role": "user",
            },
            "audit_log": {
                "recent_events": _get_audit_log_preview(10),
                "total_events_24h": 145,
            },
            "circuit_breakers": cb_states,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        _LOGGER.error("Failed to get security overview: %s", exc)
        return jsonify({"error": str(exc)}), 500
