"""Tests for Multi-Zone Coordination Engine — Slice 15."""
import pytest
from copilot_core.multizone.coordination_engine import (
    MultiZoneCoordinationEngine,
    ZoneAction,
    MultiZoneScene,
    Routine,
    Conflict,
    ConflictType,
    ResolutionStrategy,
    create_multi_zone_coordination_engine,
)


class TestMultiZoneCoordinationEngine:
    """Test multi-zone coordination engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_multi_zone_coordination_engine()
        assert engine is not None
    
    def test_create_scene(self):
        """Test scene creation."""
        engine = MultiZoneCoordinationEngine()
        
        zone_actions = {
            "zone_living_room": [
                {
                    "module_id": "licht_living_room",
                    "entity_id": "light.living_room",
                    "domain": "light",
                    "service": "turn_on",
                    "data": {"brightness": 200},
                }
            ],
            "zone_kitchen": [
                {
                    "module_id": "licht_kitchen",
                    "entity_id": "light.kitchen",
                    "domain": "light",
                    "service": "turn_on",
                    "data": {"brightness": 255},
                }
            ],
        }
        
        scene_id = engine.create_scene(
            name="Evening Mode",
            description="Lights on in living room and kitchen",
            zone_actions=zone_actions,
        )
        
        assert scene_id is not None
        assert scene_id in engine._scenes
        assert len(engine._scenes[scene_id].zone_actions) == 2
    
    def test_activate_scene(self):
        """Test scene activation."""
        engine = MultiZoneCoordinationEngine()
        
        zone_actions = {
            "zone_living_room": [
                {
                    "module_id": "licht_living_room",
                    "entity_id": "light.living_room",
                    "domain": "light",
                    "service": "turn_on",
                    "data": {},
                }
            ],
        }
        
        scene_id = engine.create_scene(
            name="Test Scene",
            description="Test",
            zone_actions=zone_actions,
        )
        
        # Activate scene
        result = engine.activate_scene(scene_id, activated_by="user_test")
        assert result is True
        
        # Verify scene is active
        assert engine._scenes[scene_id].is_active is True
        assert engine._scenes[scene_id].activated_by == "user_test"
        
        # Verify actions are pending
        pending = engine.get_pending_actions()
        assert len(pending) >= 1
    
    def test_deactivate_scene(self):
        """Test scene deactivation."""
        engine = MultiZoneCoordinationEngine()
        
        zone_actions = {
            "zone_living_room": [
                {
                    "module_id": "licht_living_room",
                    "entity_id": "light.living_room",
                    "domain": "light",
                    "service": "turn_on",
                    "data": {},
                }
            ],
        }
        
        scene_id = engine.create_scene(
            name="Test Scene",
            description="Test",
            zone_actions=zone_actions,
        )
        
        # Activate then deactivate
        engine.activate_scene(scene_id)
        result = engine.deactivate_scene(scene_id)
        
        assert result is True
        assert engine._scenes[scene_id].is_active is False
        
        # Verify actions are removed from pending
        pending = engine.get_pending_actions()
        assert len(pending) == 0
    
    def test_create_routine(self):
        """Test routine creation."""
        engine = MultiZoneCoordinationEngine()
        
        zone_actions = {
            "zone_bedroom": [
                {
                    "module_id": "licht_bedroom",
                    "entity_id": "light.bedroom",
                    "domain": "light",
                    "service": "turn_off",
                    "data": {},
                }
            ],
        }
        
        routine_id = engine.create_routine(
            name="Good Night",
            description="Turn off bedroom lights at 22:00",
            trigger_type="time",
            trigger_config={"hour": 22, "minute": 0},
            zone_actions=zone_actions,
        )
        
        assert routine_id is not None
        assert routine_id in engine._routines
        assert engine._routines[routine_id].trigger_type == "time"
        assert engine._routines[routine_id].enabled is True
    
    def test_trigger_routine(self):
        """Test routine triggering."""
        engine = MultiZoneCoordinationEngine()
        
        zone_actions = {
            "zone_entrance": [
                {
                    "module_id": "licht_entrance",
                    "entity_id": "light.entrance",
                    "domain": "light",
                    "service": "turn_on",
                    "data": {},
                }
            ],
        }
        
        routine_id = engine.create_routine(
            name="Welcome Home",
            description="Turn on entrance light",
            trigger_type="presence",
            trigger_config={"zone": "zone_entrance"},
            zone_actions=zone_actions,
        )
        
        # Trigger routine
        result = engine.trigger_routine(routine_id)
        assert result is True
        
        # Verify routine was triggered
        assert engine._routines[routine_id].trigger_count == 1
        assert engine._routines[routine_id].last_triggered is not None
        
        # Verify actions are pending
        pending = engine.get_pending_actions()
        assert len(pending) >= 1
    
    def test_disable_enable_routine(self):
        """Test routine enable/disable."""
        engine = MultiZoneCoordinationEngine()
        
        zone_actions = {
            "zone_test": [
                {
                    "module_id": "licht_test",
                    "entity_id": "light.test",
                    "domain": "light",
                    "service": "turn_on",
                    "data": {},
                }
            ],
        }
        
        routine_id = engine.create_routine(
            name="Test Routine",
            description="Test",
            trigger_type="time",
            trigger_config={"hour": 12},
            zone_actions=zone_actions,
        )
        
        # Disable
        result = engine.disable_routine(routine_id)
        assert result is True
        assert engine._routines[routine_id].enabled is False
        
        # Try to trigger disabled routine
        result = engine.trigger_routine(routine_id)
        assert result is False
        
        # Enable
        result = engine.enable_routine(routine_id)
        assert result is True
        assert engine._routines[routine_id].enabled is True
    
    def test_detect_state_conflict(self):
        """Test detection of state conflicts."""
        engine = MultiZoneCoordinationEngine()
        
        # Create scene with conflicting actions (turn_on + turn_off for same entity)
        zone_actions = {
            "zone_living_room": [
                {
                    "module_id": "licht_living_room",
                    "entity_id": "light.living_room",
                    "domain": "light",
                    "service": "turn_on",
                    "data": {},
                    "priority": 5,
                },
                {
                    "module_id": "licht_living_room",
                    "entity_id": "light.living_room",
                    "domain": "light",
                    "service": "turn_off",
                    "data": {},
                    "priority": 5,
                },
            ],
        }
        
        scene_id = engine.create_scene(
            name="Conflicting Scene",
            description="Has conflict",
            zone_actions=zone_actions,
        )
        
        scene = engine._scenes[scene_id]
        conflicts = engine._detect_scene_conflicts(scene)
        
        # Should detect state conflict
        assert len(conflicts) >= 1
        assert conflicts[0].conflict_type == ConflictType.STATE_CONFLICT
    
    def test_resolve_conflict_priority_based(self):
        """Test priority-based conflict resolution."""
        engine = MultiZoneCoordinationEngine()
        
        # Create conflicting actions with different priorities
        action1 = ZoneAction(
            action_id="action_high",
            zone_id="zone_test",
            module_id="licht_test",
            entity_id="light.test",
            domain="light",
            service="turn_on",
            priority=10,  # High priority
        )
        
        action2 = ZoneAction(
            action_id="action_low",
            zone_id="zone_test",
            module_id="licht_test",
            entity_id="light.test",
            domain="light",
            service="turn_off",
            priority=1,  # Low priority
        )
        
        engine._pending_actions["action_high"] = action1
        engine._pending_actions["action_low"] = action2
        
        conflict = Conflict(
            conflict_id="conflict_test",
            conflict_type=ConflictType.STATE_CONFLICT,
            action_ids=["action_high", "action_low"],
            description="Conflicting actions",
            resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
        )
        
        # Resolve
        result = engine._resolve_conflict(conflict)
        assert result is True
        assert conflict.resolved is True
        
        # High priority action should remain, low priority removed
        assert "action_high" in engine._pending_actions
        assert "action_low" not in engine._pending_actions
    
    def test_get_scenes(self):
        """Test getting all scenes."""
        engine = MultiZoneCoordinationEngine()
        
        # Create multiple scenes
        for i in range(3):
            engine.create_scene(
                name=f"Scene {i}",
                description=f"Test scene {i}",
                zone_actions={},
            )
        
        scenes = engine.get_scenes()
        assert len(scenes) == 3
    
    def test_get_routines(self):
        """Test getting all routines."""
        engine = MultiZoneCoordinationEngine()
        
        # Create multiple routines
        for i in range(3):
            engine.create_routine(
                name=f"Routine {i}",
                description=f"Test routine {i}",
                trigger_type="time",
                trigger_config={"hour": i},
                zone_actions={},
            )
        
        routines = engine.get_routines()
        assert len(routines) == 3
    
    def test_get_pending_actions_filtered_by_zone(self):
        """Test getting pending actions filtered by zone."""
        engine = MultiZoneCoordinationEngine()
        
        # Create actions for different zones
        action1 = ZoneAction(
            action_id="action_zone_a",
            zone_id="zone_a",
            module_id="licht_a",
            entity_id="light.a",
            domain="light",
            service="turn_on",
        )
        
        action2 = ZoneAction(
            action_id="action_zone_b",
            zone_id="zone_b",
            module_id="licht_b",
            entity_id="light.b",
            domain="light",
            service="turn_on",
        )
        
        engine._pending_actions["action_zone_a"] = action1
        engine._pending_actions["action_zone_b"] = action2
        
        # Filter by zone_a
        pending_a = engine.get_pending_actions(zone_id="zone_a")
        assert len(pending_a) == 1
        assert pending_a[0]["zone_id"] == "zone_a"
        
        # Filter by zone_b
        pending_b = engine.get_pending_actions(zone_id="zone_b")
        assert len(pending_b) == 1
        assert pending_b[0]["zone_id"] == "zone_b"
    
    def test_pending_actions_sorted_by_priority(self):
        """Test that pending actions are sorted by priority."""
        engine = MultiZoneCoordinationEngine()
        
        # Create actions with different priorities
        for i, priority in enumerate([3, 7, 1, 9, 5]):
            action = ZoneAction(
                action_id=f"action_{i}",
                zone_id="zone_test",
                module_id="licht_test",
                entity_id=f"light.test_{i}",
                domain="light",
                service="turn_on",
                priority=priority,
            )
            engine._pending_actions[f"action_{i}"] = action
        
        pending = engine.get_pending_actions()
        
        # Should be sorted by priority (highest first)
        priorities = [p["priority"] for p in pending]
        assert priorities == sorted(priorities, reverse=True)
    
    def test_scene_to_dict(self):
        """Test scene serialization."""
        scene = MultiZoneScene(
            scene_id="scene_test",
            name="Test Scene",
            description="Test description",
            zone_actions={},
            is_active=True,
            activated_at="2026-03-31T12:00:00Z",
            activated_by="user_test",
        )
        
        d = scene.to_dict()
        
        assert d["scene_id"] == "scene_test"
        assert d["name"] == "Test Scene"
        assert d["description"] == "Test description"
        assert d["is_active"] is True
        assert d["activated_at"] == "2026-03-31T12:00:00Z"
        assert d["activated_by"] == "user_test"
    
    def test_routine_to_dict(self):
        """Test routine serialization."""
        routine = Routine(
            routine_id="routine_test",
            name="Test Routine",
            description="Test description",
            trigger_type="time",
            trigger_config={"hour": 18},
            zone_actions={},
            enabled=True,
            last_triggered="2026-03-31T18:00:00Z",
            trigger_count=5,
        )
        
        d = routine.to_dict()
        
        assert d["routine_id"] == "routine_test"
        assert d["name"] == "Test Routine"
        assert d["trigger_type"] == "time"
        assert d["trigger_config"] == {"hour": 18}
        assert d["enabled"] is True
        assert d["trigger_count"] == 5
    
    def test_conflict_to_dict(self):
        """Test conflict serialization."""
        conflict = Conflict(
            conflict_id="conflict_test",
            conflict_type=ConflictType.STATE_CONFLICT,
            action_ids=["action_1", "action_2"],
            description="Test conflict",
            resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
            resolved=True,
            resolution="Priority-based resolution",
            resolved_at="2026-03-31T12:00:00Z",
        )
        
        d = conflict.to_dict()
        
        assert d["conflict_id"] == "conflict_test"
        assert d["conflict_type"] == "state_conflict"
        assert d["action_ids"] == ["action_1", "action_2"]
        assert d["resolution_strategy"] == "priority_based"
        assert d["resolved"] is True
        assert d["resolution"] == "Priority-based resolution"
    
    def test_action_to_dict(self):
        """Test action serialization."""
        action = ZoneAction(
            action_id="action_test",
            zone_id="zone_test",
            module_id="licht_test",
            entity_id="light.test",
            domain="light",
            service="turn_on",
            data={"brightness": 200},
            priority=7,
            scheduled_at="2026-03-31T18:00:00Z",
        )
        
        d = action.to_dict()
        
        assert d["action_id"] == "action_test"
        assert d["zone_id"] == "zone_test"
        assert d["domain"] == "light"
        assert d["service"] == "turn_on"
        assert d["data"] == {"brightness": 200}
        assert d["priority"] == 7
        assert d["scheduled_at"] == "2026-03-31T18:00:00Z"
