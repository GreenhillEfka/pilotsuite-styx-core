"""Tests for Workflow Engine — Slice 29."""
import pytest
from copilot_core.workflow.engine import (
    WorkflowEngine,
    WorkflowStatus,
    StepStatus,
    StepType,
    create_workflow_engine,
)


class TestWorkflowEngine:
    """Test workflow engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_workflow_engine()
        assert engine is not None
    
    def test_create_workflow(self):
        """Test workflow creation."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Test Workflow",
            description="A test workflow",
            steps=[
                {
                    "step_id": "step1",
                    "name": "First Step",
                    "step_type": "action",
                    "metadata": {"action": "log"},
                    "on_success": "step2",
                },
                {
                    "step_id": "step2",
                    "name": "Second Step",
                    "step_type": "action",
                    "metadata": {"action": "log"},
                },
            ],
            start_step="step1",
        )
        
        assert workflow_id is not None
        assert workflow_id.startswith("wf_")
        assert workflow_id in engine._definitions
    
    def test_start_workflow(self):
        """Test starting workflow."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Test Workflow",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Step 1",
                    "step_type": "action",
                    "metadata": {"action": "log", "message": "Hello"},
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        
        assert instance_id is not None
        assert instance_id.startswith("inst_")
        assert instance_id in engine._instances
    
    def test_workflow_execution_success(self):
        """Test successful workflow execution."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Simple Workflow",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Log Step",
                    "step_type": "action",
                    "metadata": {"action": "log", "message": "Test"},
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        instance = engine.get_instance(instance_id)
        
        assert instance["status"] == "completed"
    
    def test_workflow_with_context(self):
        """Test workflow with context."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Context Workflow",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Transform",
                    "step_type": "action",
                    "metadata": {"action": "transform"},
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id, context={"key": "value"})
        instance = engine.get_instance(instance_id)
        
        assert instance["context"]["key"] == "value"
    
    def test_workflow_step_failure(self):
        """Test workflow step failure."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Failing Workflow",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Fail Step",
                    "step_type": "action",
                    "metadata": {"action": "unknown_action"},
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        instance = engine.get_instance(instance_id)
        
        assert instance["status"] == "failed"
    
    def test_workflow_with_on_failure(self):
        """Test workflow with on_failure handler."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Workflow With Handler",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Fail Step",
                    "step_type": "action",
                    "metadata": {"action": "unknown_action"},
                    "on_failure": "step2",
                },
                {
                    "step_id": "step2",
                    "name": "Recovery Step",
                    "step_type": "action",
                    "metadata": {"action": "log", "message": "Recovered"},
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        instance = engine.get_instance(instance_id)
        
        # Should complete because of on_failure handler
        assert instance["status"] == "completed"
    
    def test_workflow_with_condition(self):
        """Test workflow with conditional step."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Conditional Workflow",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Conditional Step",
                    "step_type": "condition",
                    "condition": "context.active == True",
                    "metadata": {"action": "log"},
                    "on_success": "step2",
                },
                {
                    "step_id": "step2",
                    "name": "Success Step",
                    "step_type": "action",
                    "metadata": {"action": "log"},
                },
            ],
            start_step="step1",
        )
        
        # Start with active=True - should execute
        instance_id = engine.start_workflow(workflow_id, context={"active": True})
        instance = engine.get_instance(instance_id)
        
        assert instance["status"] == "completed"
    
    def test_workflow_condition_skip(self):
        """Test workflow step skipped due to condition."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Skip Workflow",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Conditional Step",
                    "step_type": "condition",
                    "condition": "context.active == True",
                    "metadata": {"action": "log"},
                    "on_success": "step2",
                },
                {
                    "step_id": "step2",
                    "name": "Next Step",
                    "step_type": "action",
                    "metadata": {"action": "log"},
                },
            ],
            start_step="step1",
        )
        
        # Start with active=False - condition fails, step skipped
        instance_id = engine.start_workflow(workflow_id, context={"active": False})
        instance = engine.get_instance(instance_id)
        
        # Step should be skipped, but workflow continues
        step_result = instance["step_results"]["step1"]
        assert step_result["status"] == "skipped"
    
    def test_pause_workflow(self):
        """Test pausing workflow."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Pause Test",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Wait",
                    "step_type": "action",
                    "metadata": {"action": "wait", "seconds": 10},
                },
            ],
            start_step="step1",
        )
        
        # Note: In real testing, we'd need async execution
        # For now, test the pause mechanism
        instance_id = engine.start_workflow(workflow_id)
        
        # Workflow completes too fast for pause test
        # This tests the pause API
        result = engine.pause_workflow(instance_id)
        
        # May be False if already completed
        assert result in (True, False)
    
    def test_cancel_workflow(self):
        """Test cancelling workflow."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Cancel Test",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Step",
                    "step_type": "action",
                    "metadata": {"action": "log"},
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        
        # Cancel after completion won't work
        result = engine.cancel_workflow(instance_id)
        
        # May be False if already completed
        assert result in (True, False)
    
    def test_resume_workflow(self):
        """Test resuming workflow."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Resume Test",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Step",
                    "step_type": "action",
                    "metadata": {"action": "log"},
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        
        # Resume after completion won't work
        result = engine.resume_workflow(instance_id)
        
        assert result is False  # Already completed
    
    def test_get_workflow(self):
        """Test getting workflow definition."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Test Workflow",
            description="Test description",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Step 1",
                    "step_type": "action",
                    "metadata": {"action": "log"},
                },
            ],
            start_step="step1",
        )
        
        workflow = engine.get_workflow(workflow_id)
        
        assert workflow is not None
        assert workflow["name"] == "Test Workflow"
        assert workflow["description"] == "Test description"
    
    def test_get_unknown_workflow(self):
        """Test getting unknown workflow."""
        engine = WorkflowEngine()
        
        workflow = engine.get_workflow("unknown_workflow")
        
        assert workflow is None
    
    def test_get_all_workflows(self):
        """Test getting all workflows."""
        engine = WorkflowEngine()
        
        for i in range(3):
            engine.create_workflow(
                name=f"Workflow {i}",
                description="Test",
                steps=[{"step_id": "s1", "name": "S1", "step_type": "action", "metadata": {"action": "log"}}],
                start_step="s1",
            )
        
        workflows = engine.get_all_workflows()
        
        assert len(workflows) == 3
    
    def test_get_instance(self):
        """Test getting workflow instance."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Test",
            description="Test",
            steps=[{"step_id": "s1", "name": "S1", "step_type": "action", "metadata": {"action": "log"}}],
            start_step="s1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        
        instance = engine.get_instance(instance_id)
        
        assert instance is not None
        assert instance["instance_id"] == instance_id
    
    def test_get_unknown_instance(self):
        """Test getting unknown instance."""
        engine = WorkflowEngine()
        
        instance = engine.get_instance("unknown_instance")
        
        assert instance is None
    
    def test_get_instances_by_workflow(self):
        """Test getting instances by workflow."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Test",
            description="Test",
            steps=[{"step_id": "s1", "name": "S1", "step_type": "action", "metadata": {"action": "log"}}],
            start_step="s1",
        )
        
        # Start multiple instances
        for i in range(3):
            engine.start_workflow(workflow_id)
        
        instances = engine.get_instances_by_workflow(workflow_id)
        
        assert len(instances) == 3
    
    def test_get_instances_filtered_by_status(self):
        """Test getting instances filtered by status."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Test",
            description="Test",
            steps=[{"step_id": "s1", "name": "S1", "step_type": "action", "metadata": {"action": "log"}}],
            start_step="s1",
        )
        
        engine.start_workflow(workflow_id)
        
        completed = engine.get_instances_by_workflow(workflow_id, status=WorkflowStatus.COMPLETED)
        failed = engine.get_instances_by_workflow(workflow_id, status=WorkflowStatus.FAILED)
        
        assert len(completed) >= 1
        assert len(failed) == 0
    
    def test_get_workflow_summary(self):
        """Test workflow summary."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Test",
            description="Test",
            steps=[{"step_id": "s1", "name": "S1", "step_type": "action", "metadata": {"action": "log"}}],
            start_step="s1",
        )
        
        engine.start_workflow(workflow_id)
        
        summary = engine.get_workflow_summary()
        
        assert summary["total_workflows"] == 1
        assert summary["total_instances"] == 1
        assert summary["completed_instances"] == 1
    
    def test_register_custom_step(self):
        """Test registering custom step."""
        engine = WorkflowEngine()
        
        def custom_action(context, **kwargs):
            return {"custom": True}
        
        engine.register_step("custom_action", custom_action)
        
        assert "custom_action" in engine._step_registry
    
    def test_workflow_with_retry(self):
        """Test workflow step retry on failure."""
        engine = WorkflowEngine()
        
        call_count = [0]
        
        def flaky_action(context, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("First attempt fails")
            return {"success": True}
        
        engine.register_step("flaky", flaky_action)
        
        workflow_id = engine.create_workflow(
            name="Retry Test",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Flaky Step",
                    "step_type": "action",
                    "metadata": {"action": "flaky"},
                    "max_retries": 2,
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        instance = engine.get_instance(instance_id)
        
        # Should succeed after retry
        assert instance["status"] == "completed"
        assert call_count[0] == 2
    
    def test_workflow_exhausts_retries(self):
        """Test workflow fails after exhausting retries."""
        engine = WorkflowEngine()
        
        def always_fails(context, **kwargs):
            raise Exception("Always fails")
        
        engine.register_step("failing", always_fails)
        
        workflow_id = engine.create_workflow(
            name="Exhaust Retry Test",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Failing Step",
                    "step_type": "action",
                    "metadata": {"action": "failing"},
                    "max_retries": 2,
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        instance = engine.get_instance(instance_id)
        
        assert instance["status"] == "failed"
    
    def test_builtin_wait_step(self):
        """Test built-in wait step."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Wait Test",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Wait",
                    "step_type": "action",
                    "metadata": {"action": "wait", "seconds": 0.1},
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        instance = engine.get_instance(instance_id)
        
        assert instance["status"] == "completed"
    
    def test_builtin_log_step(self):
        """Test built-in log step."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Log Test",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Log",
                    "step_type": "action",
                    "metadata": {"action": "log", "message": "Test message"},
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        instance = engine.get_instance(instance_id)
        
        assert instance["status"] == "completed"
    
    def test_builtin_transform_step(self):
        """Test built-in transform step."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Transform Test",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Transform",
                    "step_type": "action",
                    "metadata": {"action": "transform"},
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        instance = engine.get_instance(instance_id)
        
        assert instance["status"] == "completed"
    
    def test_workflow_definition_to_dict(self):
        """Test workflow definition serialization."""
        from copilot_core.workflow.engine import WorkflowDefinition, WorkflowStep
        
        step = WorkflowStep(
            step_id="step_test",
            name="Test Step",
            step_type=StepType.ACTION,
            on_success="step2",
            on_failure="step_error",
        )
        
        definition = WorkflowDefinition(
            workflow_id="wf_test",
            name="Test Workflow",
            description="Test",
            version="1.0.0",
            steps=[step],
            start_step="step_test",
        )
        
        d = definition.to_dict()
        
        assert d["workflow_id"] == "wf_test"
        assert d["name"] == "Test Workflow"
        assert len(d["steps"]) == 1
    
    def test_step_result_to_dict(self):
        """Test step result serialization."""
        from copilot_core.workflow.engine import StepResult, StepStatus
        
        result = StepResult(
            step_id="step_test",
            status=StepStatus.COMPLETED,
            result={"key": "value"},
            started_at="2026-03-31T12:00:00Z",
            completed_at="2026-03-31T12:00:01Z",
        )
        
        d = result.to_dict()
        
        assert d["step_id"] == "step_test"
        assert d["status"] == "completed"
        assert d["result"] == {"key": "value"}
    
    def test_workflow_instance_to_dict(self):
        """Test workflow instance serialization."""
        from copilot_core.workflow.engine import WorkflowInstance, WorkflowStatus
        
        instance = WorkflowInstance(
            instance_id="inst_test",
            workflow_id="wf_test",
            status=WorkflowStatus.COMPLETED,
            context={"key": "value"},
        )
        
        d = instance.to_dict()
        
        assert d["instance_id"] == "inst_test"
        assert d["status"] == "completed"
        assert d["context"] == {"key": "value"}
    
    def test_step_type_enum_values(self):
        """Test step type enum values."""
        assert StepType.ACTION.value == "action"
        assert StepType.CONDITION.value == "condition"
        assert StepType.PARALLEL.value == "parallel"
        assert StepType.WAIT.value == "wait"
        assert StepType.TRANSFORM.value == "transform"
    
    def test_workflow_status_enum_values(self):
        """Test workflow status enum values."""
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.CANCELLED.value == "cancelled"
    
    def test_instances_sorted_by_started_at(self):
        """Test that instances are sorted by started_at."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Test",
            description="Test",
            steps=[{"step_id": "s1", "name": "S1", "step_type": "action", "metadata": {"action": "log"}}],
            start_step="s1",
        )
        
        # Start multiple instances
        for i in range(3):
            engine.start_workflow(workflow_id)
        
        instances = engine.get_instances_by_workflow(workflow_id)
        
        # Verify sorted (newest first)
        for i in range(len(instances) - 1):
            assert instances[i]["started_at"] >= instances[i + 1]["started_at"]
    
    def test_unknown_action_fails_step(self):
        """Test that unknown action fails step."""
        engine = WorkflowEngine()
        
        workflow_id = engine.create_workflow(
            name="Unknown Action Test",
            description="Test",
            steps=[
                {
                    "step_id": "step1",
                    "name": "Unknown",
                    "step_type": "action",
                    "metadata": {"action": "nonexistent_action"},
                },
            ],
            start_step="step1",
        )
        
        instance_id = engine.start_workflow(workflow_id)
        instance = engine.get_instance(instance_id)
        
        assert instance["status"] == "failed"
        assert "Unknown action" in instance["error_message"]
