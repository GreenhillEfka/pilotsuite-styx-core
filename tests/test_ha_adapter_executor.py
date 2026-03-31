"""Tests for HA Adapter Executor — Slice 10: Decision/Execution Separation.

Tests verify:
- CommandOutput types are correct
- Execution audit trail is consistent
- HA adapter is thin (no semantic logic)
- Policy decisions are passed through correctly
"""
import pytest
from datetime import datetime, timezone
from copilot_core.homeassistant.ha_adapter_executor import (
    HAAdapterExecutor,
    CommandOutput,
    CommandStatus,
    CommandType,
    ExecutionAuditEvent,
    create_ha_adapter_executor,
)


class MockHAClient:
    """Mock HA client for testing."""
    
    def __init__(self):
        self.service_calls = []
        self.state_sets = []
    
    def call_service(self, domain: str, service: str, entity_ids: list = None, data: dict = None):
        self.service_calls.append({
            "domain": domain,
            "service": service,
            "entity_ids": entity_ids or [],
            "data": data or {},
        })
        return {"success": True}
    
    def set_state(self, entity_id: str, **kwargs):
        self.state_sets.append({"entity_id": entity_id, **kwargs})
        return {"success": True}


class MockActionIntent:
    """Mock Core ActionIntent for testing."""
    
    def __init__(self, intent_id: str, intent_type: str, domain: str = "", service: str = "", entity_ids: list = None, input_data: dict = None, policy_decision: str = ""):
        self.intent_id = intent_id
        self.intent_type = intent_type
        self.domain = domain
        self.service = service
        self.entity_ids = entity_ids or []
        self.input_data = input_data or {}
        self.policy_decision = policy_decision


class TestCommandOutput:
    """Test CommandOutput dataclass."""
    
    def test_command_output_defaults(self):
        output = CommandOutput()
        assert output.command_id == ""
        assert output.command_type == CommandType.SERVICE_CALL
        assert output.status == CommandStatus.PENDING
        assert output.entity_ids == []
        assert output.input_data == {}
        assert output.output_data == {}
        assert output.execution_time_ms == 0
        assert output.error_message == ""
        assert output.policy_decision == ""
        assert output.audit_trail == []
        assert output.completed_at is None
    
    def test_command_output_to_dict(self):
        output = CommandOutput(
            command_id="test_123",
            command_type=CommandType.STATE_SET,
            status=CommandStatus.SUCCESS,
            domain="light",
            service="turn_on",
            entity_ids=["light.living_room"],
            input_data={"brightness": 200},
            output_data={"result": "ok"},
            execution_time_ms=42,
            policy_decision="policy_allowed",
        )
        
        d = output.to_dict()
        assert d["command_id"] == "test_123"
        assert d["command_type"] == "state_set"
        assert d["status"] == "success"
        assert d["domain"] == "light"
        assert d["service"] == "turn_on"
        assert d["entity_ids"] == ["light.living_room"]
        assert d["input_data"] == {"brightness": 200}
        assert d["output_data"] == {"result": "ok"}
        assert d["execution_time_ms"] == 42
        assert d["policy_decision"] == "policy_allowed"
        assert d["completed_at"] is not None


class TestExecutionAuditEvent:
    """Test ExecutionAuditEvent dataclass."""
    
    def test_audit_event_defaults(self):
        event = ExecutionAuditEvent()
        assert event.event_type == ""
        assert event.actor == ""
        assert event.action == ""
        assert event.reason == ""
        assert event.data == {}
        assert event.timestamp is not None
    
    def test_audit_event_to_dict(self):
        event = ExecutionAuditEvent(
            event_type="execution_started",
            actor="HAAdapterExecutor",
            action="execute_service_call",
            reason="Core intent: test_123",
            data={"command_id": "test_123", "domain": "light"},
        )
        
        d = event.to_dict()
        assert d["event_type"] == "execution_started"
        assert d["actor"] == "HAAdapterExecutor"
        assert d["action"] == "execute_service_call"
        assert d["reason"] == "Core intent: test_123"
        assert d["data"] == {"command_id": "test_123", "domain": "light"}


class TestHAAdapterExecutor:
    """Test HA adapter executor."""
    
    def test_create_executor(self):
        mock_ha = MockHAClient()
        executor = create_ha_adapter_executor(mock_ha)
        assert executor.ha_client is mock_ha
    
    def test_execute_service_call_success(self):
        mock_ha = MockHAClient()
        executor = HAAdapterExecutor(mock_ha)
        
        intent = MockActionIntent(
            intent_id="cmd_001",
            intent_type="service_call",
            domain="light",
            service="turn_on",
            entity_ids=["light.living_room", "light.kitchen"],
            input_data={"brightness": 200},
            policy_decision="policy_allowed",
        )
        
        output = executor.execute_command(intent)
        
        assert output.command_id == "cmd_001"
        assert output.command_type == CommandType.SERVICE_CALL
        assert output.status == CommandStatus.SUCCESS
        assert output.domain == "light"
        assert output.service == "turn_on"
        assert output.entity_ids == ["light.living_room", "light.kitchen"]
        assert output.input_data == {"brightness": 200}
        assert output.policy_decision == "policy_allowed"
        assert output.error_message == ""
        assert output.completed_at is not None
        assert output.execution_time_ms >= 0
        
        # Verify HA client was called correctly
        assert len(mock_ha.service_calls) == 1
        call = mock_ha.service_calls[0]
        assert call["domain"] == "light"
        assert call["service"] == "turn_on"
        assert call["entity_ids"] == ["light.living_room", "light.kitchen"]
        assert call["data"] == {"brightness": 200}
    
    def test_execute_state_set_success(self):
        mock_ha = MockHAClient()
        executor = HAAdapterExecutor(mock_ha)
        
        intent = MockActionIntent(
            intent_id="cmd_002",
            intent_type="state_set",
            domain="climate",
            service="",
            entity_ids=["climate.living_room"],
            input_data={"temperature": 22.0},
            policy_decision="policy_allowed",
        )
        
        output = executor.execute_command(intent)
        
        assert output.command_id == "cmd_002"
        assert output.command_type == CommandType.STATE_SET
        assert output.status == CommandStatus.SUCCESS
        assert output.entity_ids == ["climate.living_room"]
        
        # Verify HA client was called
        assert len(mock_ha.state_sets) == 1
        state = mock_ha.state_sets[0]
        assert state["entity_id"] == "climate.living_room"
    
    def test_execute_scene_activate(self):
        mock_ha = MockHAClient()
        executor = HAAdapterExecutor(mock_ha)
        
        intent = MockActionIntent(
            intent_id="cmd_003",
            intent_type="scene_activate",
            domain="scene",
            service="turn_on",
            entity_ids=["scene.movie_night"],
            policy_decision="policy_allowed",
        )
        
        output = executor.execute_command(intent)
        
        assert output.command_id == "cmd_003"
        assert output.command_type == CommandType.SCENE_ACTIVATE
        assert output.status == CommandStatus.SUCCESS
    
    def test_execute_script(self):
        mock_ha = MockHAClient()
        executor = HAAdapterExecutor(mock_ha)
        
        intent = MockActionIntent(
            intent_id="cmd_004",
            intent_type="script_execute",
            domain="script",
            service="turn_on",
            entity_ids=["script.good_morning"],
            policy_decision="policy_allowed",
        )
        
        output = executor.execute_command(intent)
        
        assert output.command_id == "cmd_004"
        assert output.command_type == CommandType.SCRIPT_EXECUTE
        assert output.status == CommandStatus.SUCCESS
    
    def test_execute_automation_trigger(self):
        mock_ha = MockHAClient()
        executor = HAAdapterExecutor(mock_ha)
        
        intent = MockActionIntent(
            intent_id="cmd_005",
            intent_type="automation_trigger",
            domain="automation",
            service="trigger",
            entity_ids=["automation.welcome_home"],
            policy_decision="policy_allowed",
        )
        
        output = executor.execute_command(intent)
        
        assert output.command_id == "cmd_005"
        assert output.command_type == CommandType.AUTOMATION_TRIGGER
        assert output.status == CommandStatus.SUCCESS
    
    def test_execute_with_missing_ha_client(self):
        executor = HAAdapterExecutor(ha_client=None)
        
        intent = MockActionIntent(
            intent_id="cmd_006",
            intent_type="service_call",
            domain="light",
            service="turn_on",
            entity_ids=["light.test"],
        )
        
        output = executor.execute_command(intent)
        
        assert output.status == CommandStatus.FAILED
        assert "HA client not available" in output.error_message
    
    def test_audit_trail_is_populated(self):
        mock_ha = MockHAClient()
        executor = HAAdapterExecutor(mock_ha)
        
        intent = MockActionIntent(
            intent_id="cmd_007",
            intent_type="service_call",
            domain="light",
            service="turn_on",
            entity_ids=["light.test"],
        )
        
        executor.execute_command(intent)
        
        audit_trail = executor.get_audit_trail()
        assert len(audit_trail) >= 1
        
        # Check for execution_started event
        start_events = [e for e in audit_trail if e.get("event_type") == "execution_started"]
        assert len(start_events) >= 1
        
        # Check for execution_succeeded event
        success_events = [e for e in audit_trail if e.get("event_type") == "execution_succeeded"]
        assert len(success_events) >= 1
    
    def test_audit_trail_filtered_by_command_id(self):
        mock_ha = MockHAClient()
        executor = HAAdapterExecutor(mock_ha)
        
        intent1 = MockActionIntent(intent_id="cmd_A", intent_type="service_call", domain="light", service="turn_on", entity_ids=["light.a"])
        intent2 = MockActionIntent(intent_id="cmd_B", intent_type="service_call", domain="light", service="turn_on", entity_ids=["light.b"])
        
        executor.execute_command(intent1)
        executor.execute_command(intent2)
        
        # Filter by command_id
        trail_a = executor.get_audit_trail(command_id="cmd_A")
        trail_b = executor.get_audit_trail(command_id="cmd_B")
        
        assert all(e.get("data", {}).get("command_id") == "cmd_A" for e in trail_a)
        assert all(e.get("data", {}).get("command_id") == "cmd_B" for e in trail_b)
    
    def test_default_intent_type_maps_to_service_call(self):
        mock_ha = MockHAClient()
        executor = HAAdapterExecutor(mock_ha)
        
        intent = MockActionIntent(
            intent_id="cmd_008",
            intent_type="unknown_type",  # Unknown type
            domain="switch",
            service="turn_on",
            entity_ids=["switch.test"],
        )
        
        output = executor.execute_command(intent)
        
        # Should default to SERVICE_CALL
        assert output.command_type == CommandType.SERVICE_CALL
        assert output.status == CommandStatus.SUCCESS


class TestDecisionExecutionSeparation:
    """Test that decision/execution separation is enforced."""
    
    def test_executor_is_thin_adapter_no_semantic_logic(self):
        """Verify HAAdapterExecutor has no decision logic."""
        mock_ha = MockHAClient()
        executor = HAAdapterExecutor(mock_ha)
        
        # Executor should only have execution methods, no policy/decision methods
        methods = dir(executor)
        
        # Should NOT have policy methods
        assert "check_policy" not in methods
        assert "evaluate_eligibility" not in methods
        assert "make_decision" not in methods
        
        # Should ONLY have execution methods
        assert "execute_command" in methods
        assert "_execute_service_call" in methods
        assert "_execute_state_set" in methods
    
    def test_policy_decision_is_passed_through_not_evaluated(self):
        """Verify policy decision from Core is passed through unchanged."""
        mock_ha = MockHAClient()
        executor = HAAdapterExecutor(mock_ha)
        
        intent = MockActionIntent(
            intent_id="cmd_009",
            intent_type="service_call",
            domain="light",
            service="turn_on",
            entity_ids=["light.test"],
            policy_decision="CORE_DECISION_123",
        )
        
        output = executor.execute_command(intent)
        
        # Policy decision should be passed through unchanged
        assert output.policy_decision == "CORE_DECISION_123"
    
    def test_audit_trail_shows_core_as_decision_maker(self):
        """Verify audit trail shows Core as decision maker, not HA adapter."""
        mock_ha = MockHAClient()
        executor = HAAdapterExecutor(mock_ha)
        
        intent = MockActionIntent(
            intent_id="cmd_010",
            intent_type="service_call",
            domain="light",
            service="turn_on",
            entity_ids=["light.test"],
            policy_decision="policy_allowed",
        )
        
        executor.execute_command(intent)
        
        audit_trail = executor.get_audit_trail()
        
        # All audit events should show HAAdapterExecutor as actor (executor, not decider)
        for event in audit_trail:
            assert event["actor"] == "HAAdapterExecutor"
            # Reason should reference Core intent, not HA decision
            assert "Core intent" in event.get("reason", "") or "command" in event.get("reason", "").lower()
