"""HA Adapter Command Outputs — Formalized execution layer.

Slice 10: Decision/Execution Separation

Core decides eligibility and policy. HA executes via thin adapters.
This module provides the canonical command output types for HA execution.

Key principles:
- Core produces ActionIntents (what + why)
- HA adapters produce CommandOutputs (how + result)
- Policy is NOT duplicated in HA/frontend code
- Audit trail is consistent across all execution outcomes
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CommandStatus(Enum):
    """Execution status of HA adapter command."""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    BLOCKED_BY_POLICY = "blocked_by_policy"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class CommandType(Enum):
    """Type of HA adapter command."""
    SERVICE_CALL = "service_call"
    STATE_SET = "state_set"
    SCENE_ACTIVATE = "scene_activate"
    SCRIPT_EXECUTE = "script_execute"
    AUTOMATION_TRIGGER = "automation_trigger"


@dataclass
class CommandOutput:
    """Result of HA adapter command execution.
    
    This is the canonical output type for all HA execution.
    Core produces ActionIntents → HA adapters produce CommandOutputs.
    
    Fields:
        command_id: Unique identifier for this command
        command_type: Type of command executed
        status: Execution status
        domain: HA domain (light, switch, climate, etc.)
        service: HA service (turn_on, turn_off, set_temperature, etc.)
        entity_ids: Target entities
        input_data: Original input data sent to HA
        output_data: Raw output data from HA
        execution_time_ms: Time taken to execute
        error_message: Error message if failed
        policy_decision: Policy decision that led to this execution
        audit_trail: List of audit events for this command
        created_at: When this command was created
        completed_at: When this command completed
    """
    command_id: str = ""
    command_type: CommandType = CommandType.SERVICE_CALL
    status: CommandStatus = CommandStatus.PENDING
    domain: str = ""
    service: str = ""
    entity_ids: List[str] = field(default_factory=list)
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: int = 0
    error_message: str = ""
    policy_decision: str = ""
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        completed_at = self.completed_at
        if completed_at is None and self.status != CommandStatus.PENDING:
            completed_at = self.created_at

        return {
            "command_id": self.command_id,
            "command_type": self.command_type.value,
            "status": self.status.value,
            "domain": self.domain,
            "service": self.service,
            "entity_ids": self.entity_ids,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
            "policy_decision": self.policy_decision,
            "audit_trail": self.audit_trail,
            "created_at": self.created_at,
            "completed_at": completed_at,
        }


@dataclass
class ExecutionAuditEvent:
    """Single audit event for execution trail.
    
    All execution outcomes must produce consistent audit events.
    
    Fields:
        event_type: Type of audit event
        timestamp: When this event occurred
        actor: Who/what triggered this (Core, HA adapter, policy engine)
        action: What action was taken
        reason: Why this action was taken
        data: Additional event data
    """
    event_type: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    actor: str = ""
    action: str = ""
    reason: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "reason": self.reason,
            "data": self.data,
        }


class HAAdapterExecutor:
    """Thin adapter layer for HA command execution.
    
    This is NOT a semantic owner. It only executes commands from Core.
    All decision logic lives in Core (policy, eligibility, etc.).
    
    Usage:
        executor = HAAdapterExecutor(ha_client)
        output = executor.execute_command(intent)
    """
    
    def __init__(self, ha_client: Optional[Any] = None):
        self.ha_client = ha_client
        self._execution_count = 0
        self._audit_log: List[ExecutionAuditEvent] = []
    
    def execute_command(self, intent: Any) -> CommandOutput:
        """Execute a command from Core ActionIntent.
        
        Args:
            intent: ActionIntent from Core (contains what + why)
        
        Returns:
            CommandOutput with execution result (how + result)
        """
        import time
        start_time = time.time()
        
        # Extract command details from intent
        command_id = getattr(intent, "intent_id", f"cmd_{self._execution_count}")
        command_type = self._map_intent_to_command_type(intent)
        domain = getattr(intent, "domain", "")
        service = getattr(intent, "service", "")
        entity_ids = getattr(intent, "entity_ids", [])
        input_data = getattr(intent, "input_data", {})
        policy_decision = getattr(intent, "policy_decision", "")
        
        # Create output with pending status
        output = CommandOutput(
            command_id=command_id,
            command_type=command_type,
            status=CommandStatus.EXECUTING,
            domain=domain,
            service=service,
            entity_ids=entity_ids,
            input_data=input_data,
            policy_decision=policy_decision,
        )
        
        # Add audit event: execution started
        self._add_audit_event(ExecutionAuditEvent(
            event_type="execution_started",
            actor="HAAdapterExecutor",
            action=f"execute_{command_type.value}",
            reason=f"Core intent: {command_id}",
            data={"command_id": command_id, "domain": domain, "service": service},
        ))
        
        # Execute via HA client
        try:
            if not self.ha_client:
                raise RuntimeError("HA client not available")
            
            # Execute based on command type
            if command_type == CommandType.SERVICE_CALL:
                result = self._execute_service_call(domain, service, entity_ids, input_data)
            elif command_type == CommandType.STATE_SET:
                result = self._execute_state_set(entity_ids, input_data)
            elif command_type == CommandType.SCENE_ACTIVATE:
                result = self._execute_scene_activate(entity_ids)
            elif command_type == CommandType.SCRIPT_EXECUTE:
                result = self._execute_script(entity_ids)
            elif command_type == CommandType.AUTOMATION_TRIGGER:
                result = self._execute_automation_trigger(entity_ids)
            else:
                raise ValueError(f"Unknown command type: {command_type}")
            
            # Mark success
            output.status = CommandStatus.SUCCESS
            output.output_data = result
            output.execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Add audit event: execution succeeded
            self._add_audit_event(ExecutionAuditEvent(
                event_type="execution_succeeded",
                actor="HAAdapterExecutor",
                action="execute_complete",
                reason=f"Command {command_id} completed successfully",
                data={"command_id": command_id, "execution_time_ms": output.execution_time_ms},
            ))
            
        except Exception as exc:
            # Mark failure
            output.status = CommandStatus.FAILED
            output.error_message = str(exc)
            output.execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Add audit event: execution failed
            self._add_audit_event(ExecutionAuditEvent(
                event_type="execution_failed",
                actor="HAAdapterExecutor",
                action="execute_failed",
                reason=f"Command {command_id} failed: {exc}",
                data={"command_id": command_id, "error": str(exc)},
            ))
            
            logger.exception("HA adapter command failed: %s", command_id)
        
        # Set completion timestamp
        output.completed_at = datetime.now(timezone.utc).isoformat()
        self._execution_count += 1
        
        return output
    
    def _map_intent_to_command_type(self, intent: Any) -> CommandType:
        """Map Core ActionIntent to CommandType."""
        intent_type = getattr(intent, "intent_type", "")
        
        if intent_type in ("service_call", "call_service"):
            return CommandType.SERVICE_CALL
        elif intent_type in ("state_set", "set_state"):
            return CommandType.STATE_SET
        elif intent_type in ("scene_activate", "activate_scene"):
            return CommandType.SCENE_ACTIVATE
        elif intent_type in ("script_execute", "execute_script"):
            return CommandType.SCRIPT_EXECUTE
        elif intent_type in ("automation_trigger", "trigger_automation"):
            return CommandType.AUTOMATION_TRIGGER
        else:
            # Default to service call
            return CommandType.SERVICE_CALL
    
    def _execute_service_call(self, domain: str, service: str, entity_ids: List[str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HA service call."""
        if not self.ha_client:
            raise RuntimeError("HA client not available")
        
        # Call HA service
        result = self.ha_client.call_service(
            domain=domain,
            service=service,
            entity_ids=entity_ids,
            data=data,
        )
        
        return {"result": result, "type": "service_call"}
    
    def _execute_state_set(self, entity_ids: List[str], data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HA state set."""
        if not self.ha_client:
            raise RuntimeError("HA client not available")
        
        results = []
        for entity_id in entity_ids:
            result = self.ha_client.set_state(entity_id=entity_id, **data)
            results.append({"entity_id": entity_id, "result": result})
        
        return {"results": results, "type": "state_set"}
    
    def _execute_scene_activate(self, entity_ids: List[str]) -> Dict[str, Any]:
        """Execute HA scene activation."""
        if not self.ha_client:
            raise RuntimeError("HA client not available")
        
        results = []
        for scene_id in entity_ids:
            result = self.ha_client.call_service("scene", "turn_on", entity_ids=[scene_id])
            results.append({"scene_id": scene_id, "result": result})
        
        return {"results": results, "type": "scene_activate"}
    
    def _execute_script(self, entity_ids: List[str]) -> Dict[str, Any]:
        """Execute HA script."""
        if not self.ha_client:
            raise RuntimeError("HA client not available")
        
        results = []
        for script_id in entity_ids:
            result = self.ha_client.call_service("script", "turn_on", entity_ids=[script_id])
            results.append({"script_id": script_id, "result": result})
        
        return {"results": results, "type": "script_execute"}
    
    def _execute_automation_trigger(self, entity_ids: List[str]) -> Dict[str, Any]:
        """Execute HA automation trigger."""
        if not self.ha_client:
            raise RuntimeError("HA client not available")
        
        results = []
        for automation_id in entity_ids:
            result = self.ha_client.call_service("automation", "trigger", entity_ids=[automation_id])
            results.append({"automation_id": automation_id, "result": result})
        
        return {"results": results, "type": "automation_trigger"}
    
    def _add_audit_event(self, event: ExecutionAuditEvent) -> None:
        """Add audit event to log."""
        self._audit_log.append(event)
        
        # Trim log if too large (keep last 1000 events)
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-1000:]
    
    def get_audit_trail(self, command_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get audit trail, optionally filtered by command_id."""
        if command_id:
            return [e.to_dict() for e in self._audit_log if e.data.get("command_id") == command_id]
        return [e.to_dict() for e in self._audit_log]


def create_ha_adapter_executor(ha_client: Optional[Any] = None) -> HAAdapterExecutor:
    """Factory function to create HA adapter executor.
    
    This is the canonical entry point for Slice 10.
    """
    return HAAdapterExecutor(ha_client=ha_client)
