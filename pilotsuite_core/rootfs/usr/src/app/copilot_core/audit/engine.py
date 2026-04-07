"""Audit Engine — Slice 36.

Security audit logging for PilotSuite Core.

Features:
- Immutable audit log
- Event categorization
- User action tracking
- Security event detection
- Audit trail export
- Compliance reporting
"""
from __future__ import annotations

import logging
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Audit event type."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    CONFIG_CHANGE = "config_change"
    SECURITY_EVENT = "security_event"
    SYSTEM_EVENT = "system_event"
    USER_ACTION = "user_action"
    API_CALL = "api_call"


class AuditSeverity(Enum):
    """Audit event severity."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event record."""
    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: str
    actor_id: str
    actor_type: str  # user, system, service
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Dict[str, Any]
    ip_address: Optional[str]
    user_agent: Optional[str]
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    hash: str = ""
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute hash for integrity verification."""
        data = {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "actor_id": self.actor_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "hash": self.hash,
        }


@dataclass
class AuditQuery:
    """Audit log query."""
    event_type: Optional[AuditEventType] = None
    severity: Optional[AuditSeverity] = None
    actor_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = 100
    offset: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value if self.event_type else None,
            "severity": self.severity.value if self.severity else None,
            "actor_id": self.actor_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "limit": self.limit,
            "offset": self.offset,
        }


class AuditEngine:
    """Security audit logging engine."""
    
    def __init__(self, max_events: int = 100000):
        self._events: List[AuditEvent] = []
        self._max_events = max_events
        self._event_index: Dict[str, AuditEvent] = {}
        
        # Statistics
        self._stats = {
            "total_events": 0,
            "by_type": {},
            "by_severity": {},
            "by_actor": {},
        }
    
    def log(self, event_type: AuditEventType, action: str,
            actor_id: str, actor_type: str = "user",
            severity: AuditSeverity = AuditSeverity.INFO,
            resource_type: Optional[str] = None,
            resource_id: Optional[str] = None,
            details: Optional[Dict[str, Any]] = None,
            ip_address: Optional[str] = None,
            user_agent: Optional[str] = None,
            previous_state: Optional[Dict[str, Any]] = None,
            new_state: Optional[Dict[str, Any]] = None) -> str:
        """Log an audit event."""
        event_id = f"audit_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            severity=severity,
            timestamp=timestamp,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            previous_state=previous_state,
            new_state=new_state,
        )
        
        # Store event
        self._events.append(event)
        self._event_index[event_id] = event
        
        # Update statistics
        self._update_stats(event)
        
        # Trim if needed
        if len(self._events) > self._max_events:
            removed = self._events[:len(self._events) - self._max_events]
            self._events = self._events[-self._max_events:]
            for r in removed:
                if r.event_id in self._event_index:
                    del self._event_index[r.event_id]
        
        logger.info("Audit event logged: %s - %s by %s", event_type.value, action, actor_id)
        
        return event_id
    
    def _update_stats(self, event: AuditEvent) -> None:
        """Update statistics."""
        self._stats["total_events"] += 1
        
        # By type
        event_type = event.event_type.value
        self._stats["by_type"][event_type] = self._stats["by_type"].get(event_type, 0) + 1
        
        # By severity
        severity = event.severity.value
        self._stats["by_severity"][severity] = self._stats["by_severity"].get(severity, 0) + 1
        
        # By actor
        actor = event.actor_id
        self._stats["by_actor"][actor] = self._stats["by_actor"].get(actor, 0) + 1
    
    def log_authentication(self, actor_id: str, success: bool,
                        method: str = "password",
                        ip_address: Optional[str] = None,
                        details: Optional[Dict[str, Any]] = None) -> str:
        """Log authentication event."""
        return self.log(
            event_type=AuditEventType.AUTHENTICATION,
            action="login" if success else "login_failed",
            actor_id=actor_id,
            severity=AuditSeverity.WARNING if not success else AuditSeverity.INFO,
            ip_address=ip_address,
            details={**(details or {}), "method": method, "success": success},
        )
    
    def log_authorization(self, actor_id: str, resource_type: str,
                         resource_id: str, action: str,
                         granted: bool,
                         details: Optional[Dict[str, Any]] = None) -> str:
        """Log authorization event."""
        return self.log(
            event_type=AuditEventType.AUTHORIZATION,
            action="access_denied" if not granted else "access_granted",
            actor_id=actor_id,
            severity=AuditSeverity.WARNING if not granted else AuditSeverity.INFO,
            resource_type=resource_type,
            resource_id=resource_id,
            details={**(details or {}), "granted": granted},
        )
    
    def log_data_access(self, actor_id: str, resource_type: str,
                       resource_id: str,
                       details: Optional[Dict[str, Any]] = None) -> str:
        """Log data access event."""
        return self.log(
            event_type=AuditEventType.DATA_ACCESS,
            action="read",
            actor_id=actor_id,
            severity=AuditSeverity.INFO,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )
    
    def log_data_modification(self, actor_id: str, resource_type: str,
                             resource_id: str,
                             previous_state: Dict[str, Any],
                             new_state: Dict[str, Any],
                             details: Optional[Dict[str, Any]] = None) -> str:
        """Log data modification event."""
        return self.log(
            event_type=AuditEventType.DATA_MODIFICATION,
            action="update",
            actor_id=actor_id,
            severity=AuditSeverity.INFO,
            resource_type=resource_type,
            resource_id=resource_id,
            previous_state=previous_state,
            new_state=new_state,
            details=details or {},
        )
    
    def log_data_deletion(self, actor_id: str, resource_type: str,
                         resource_id: str,
                         previous_state: Optional[Dict[str, Any]] = None,
                         details: Optional[Dict[str, Any]] = None) -> str:
        """Log data deletion event."""
        return self.log(
            event_type=AuditEventType.DATA_DELETION,
            action="delete",
            actor_id=actor_id,
            severity=AuditSeverity.INFO,
            resource_type=resource_type,
            resource_id=resource_id,
            previous_state=previous_state,
            details=details or {},
        )
    
    def log_config_change(self, actor_id: str, config_key: str,
                         previous_value: Any, new_value: Any,
                         details: Optional[Dict[str, Any]] = None) -> str:
        """Log configuration change event."""
        return self.log(
            event_type=AuditEventType.CONFIG_CHANGE,
            action="config_update",
            actor_id=actor_id,
            severity=AuditSeverity.INFO,
            resource_type="config",
            resource_id=config_key,
            previous_state={"value": previous_value},
            new_state={"value": new_value},
            details=details or {},
        )
    
    def log_security_event(self, actor_id: str, action: str,
                          severity: AuditSeverity = AuditSeverity.WARNING,
                          details: Optional[Dict[str, Any]] = None) -> str:
        """Log security event."""
        return self.log(
            event_type=AuditEventType.SECURITY_EVENT,
            action=action,
            actor_id=actor_id,
            severity=severity,
            details=details or {},
        )
    
    def log_system_event(self, action: str,
                        actor_id: str = "system",
                        severity: AuditSeverity = AuditSeverity.INFO,
                        details: Optional[Dict[str, Any]] = None) -> str:
        """Log system event."""
        return self.log(
            event_type=AuditEventType.SYSTEM_EVENT,
            action=action,
            actor_id=actor_id,
            severity=severity,
            details=details or {},
        )
    
    def log_api_call(self, actor_id: str, endpoint: str,
                    method: str = "GET",
                    status_code: int = 200,
                    ip_address: Optional[str] = None,
                    user_agent: Optional[str] = None,
                    details: Optional[Dict[str, Any]] = None) -> str:
        """Log API call event."""
        return self.log(
            event_type=AuditEventType.API_CALL,
            action=f"{method} {endpoint}",
            actor_id=actor_id,
            severity=AuditSeverity.WARNING if status_code >= 400 else AuditSeverity.INFO,
            ip_address=ip_address,
            user_agent=user_agent,
            details={**(details or {}), "status_code": status_code, "method": method, "endpoint": endpoint},
        )
    
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event by ID."""
        if event_id not in self._event_index:
            return None
        
        return self._event_index[event_id].to_dict()
    
    def query(self, query: AuditQuery) -> List[Dict[str, Any]]:
        """Query audit log."""
        results = []
        
        for event in self._events:
            # Apply filters
            if query.event_type and event.event_type != query.event_type:
                continue
            
            if query.severity and event.severity != query.severity:
                continue
            
            if query.actor_id and event.actor_id != query.actor_id:
                continue
            
            if query.resource_type and event.resource_type != query.resource_type:
                continue
            
            if query.resource_id and event.resource_id != query.resource_id:
                continue
            
            if query.action and query.action not in event.action:
                continue
            
            if query.start_time:
                start = datetime.fromisoformat(query.start_time)
                event_time = datetime.fromisoformat(event.timestamp)
                if event_time < start:
                    continue
            
            if query.end_time:
                end = datetime.fromisoformat(query.end_time)
                event_time = datetime.fromisoformat(event.timestamp)
                if event_time > end:
                    continue
            
            results.append(event)
        
        # Sort by timestamp (newest first)
        results.sort(key=lambda e: e.timestamp, reverse=True)
        
        # Apply pagination
        results = results[query.offset:query.offset + query.limit]
        
        return [e.to_dict() for e in results]
    
    def get_events_by_actor(self, actor_id: str,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """Get events for a specific actor."""
        query = AuditQuery(actor_id=actor_id, limit=limit)
        return self.query(query)
    
    def get_events_by_resource(self, resource_type: str,
                              resource_id: str,
                              limit: int = 100) -> List[Dict[str, Any]]:
        """Get events for a specific resource."""
        query = AuditQuery(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )
        return self.query(query)
    
    def get_events_by_type(self, event_type: AuditEventType,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get events by type."""
        query = AuditQuery(event_type=event_type, limit=limit)
        return self.query(query)
    
    def get_security_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get security events."""
        query = AuditQuery(event_type=AuditEventType.SECURITY_EVENT, limit=limit)
        return self.query(query)
    
    def get_failed_authentications(self, actor_id: Optional[str] = None,
                                  limit: int = 100) -> List[Dict[str, Any]]:
        """Get failed authentication attempts."""
        events = []
        
        for event in self._events:
            if event.event_type != AuditEventType.AUTHENTICATION:
                continue
            
            if event.details.get("success") is not False:
                continue
            
            if actor_id and event.actor_id != actor_id:
                continue
            
            events.append(event)
            
            if len(events) >= limit:
                break
        
        return [e.to_dict() for e in events]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get audit statistics."""
        return {
            **self._stats,
            "stored_events": len(self._events),
            "max_events": self._max_events,
        }
    
    def export_events(self, format: str = "json",
                     start_time: Optional[str] = None,
                     end_time: Optional[str] = None) -> str:
        """Export audit events."""
        query = AuditQuery(start_time=start_time, end_time=end_time, limit=self._max_events)
        events = self.query(query)
        
        if format == "json":
            return json.dumps(events, indent=2)
        
        elif format == "csv":
            if not events:
                return ""
            
            import csv
            import io
            
            output = io.StringIO()
            fieldnames = ["event_id", "timestamp", "event_type", "severity", 
                         "actor_id", "action", "resource_type", "resource_id"]
            
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            for event in events:
                writer.writerow(event)
            
            return output.getvalue()
        
        return json.dumps(events, indent=2)
    
    def verify_integrity(self) -> Dict[str, Any]:
        """Verify audit log integrity."""
        valid = 0
        invalid = 0
        
        for event in self._events:
            expected_hash = event._compute_hash()
            if event.hash == expected_hash:
                valid += 1
            else:
                invalid += 1
        
        return {
            "total_events": len(self._events),
            "valid": valid,
            "invalid": invalid,
            "integrity_ok": invalid == 0,
        }
    
    def clear(self, older_than: Optional[str] = None) -> int:
        """Clear audit log (optionally older than timestamp)."""
        if older_than is None:
            count = len(self._events)
            self._events.clear()
            self._event_index.clear()
            return count
        
        # Clear events older than timestamp
        cutoff = datetime.fromisoformat(older_than)
        
        initial_count = len(self._events)
        self._events = [
            e for e in self._events
            if datetime.fromisoformat(e.timestamp) >= cutoff
        ]
        
        # Rebuild index
        self._event_index = {e.event_id: e for e in self._events}
        
        return initial_count - len(self._events)


def create_audit_engine(max_events: int = 100000) -> AuditEngine:
    """Factory function to create audit engine."""
    return AuditEngine(max_events=max_events)
