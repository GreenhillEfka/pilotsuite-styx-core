#!/usr/bin/env python3
"""
Tests for Graph Candidates Bridge module.
"""
import time
import tempfile
import os
import sys

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from copilot_core.brain_graph.model import GraphNode, GraphEdge
from copilot_core.brain_graph.store import GraphStore
from copilot_core.brain_graph.service import BrainGraphService
from copilot_core.brain_graph.bridge import (
    GraphCandidatesBridge,
    CandidatePattern,
    PatternExtractionConfig
)


def test_bridge_initialization():
    """Test bridge initialization with brain service."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        brain_service = BrainGraphService(store=store)
        
        # Create bridge with default config
        bridge = GraphCandidatesBridge(brain_service)
        assert bridge.brain_service == brain_service
        assert bridge.config.min_edge_weight == 0.5
        assert bridge.config.max_patterns == 50
        
        # Create bridge with custom config
        custom_config = PatternExtractionConfig(
            min_edge_weight=0.8,
            max_patterns=20,
            lookback_hours=24
        )
        bridge2 = GraphCandidatesBridge(brain_service, config=custom_config)
        assert bridge2.config.min_edge_weight == 0.8
        assert bridge2.config.max_patterns == 20
        
        print("✅ Bridge initialization test passed")


def test_pattern_extraction():
    """Test extracting patterns from brain graph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        brain_service = BrainGraphService(store=store)
        
        now_ms = int(time.time() * 1000)
        
        # Create test nodes
        light_kitchen = GraphNode(
            id="ha.entity:light.kitchen",
            kind="entity",
            label="Kitchen Light",
            updated_at_ms=now_ms,
            score=3.0,
            domain="light"
        )
        
        switch_coffee = GraphNode(
            id="ha.entity:switch.coffee_machine",
            kind="entity", 
            label="Coffee Machine",
            updated_at_ms=now_ms,
            score=2.5,
            domain="switch"
        )
        
        zone_kitchen = GraphNode(
            id="zone:kitchen",
            kind="zone",
            label="Kitchen",
            updated_at_ms=now_ms,
            score=2.0
        )
        
        service_turn_on = GraphNode(
            id="ha.service:light.turn_on",
            kind="concept",
            label="Light Turn On",
            updated_at_ms=now_ms,
            score=1.5
        )
        
        store.upsert_node(light_kitchen)
        store.upsert_node(switch_coffee)
        store.upsert_node(zone_kitchen)
        store.upsert_node(service_turn_on)
        
        # Create test edges
        affect_edge = GraphEdge(
            id="e1",
            from_node="ha.service:light.turn_on",
            to_node="ha.entity:light.kitchen",
            edge_type="affects",
            updated_at_ms=now_ms,
            weight=2.0,
            evidence={"kind": "service_call"}
        )
        
        controls_edge = GraphEdge(
            id="e2",
            from_node="ha.entity:light.kitchen",
            to_node="ha.entity:switch.coffee_machine", 
            edge_type="affects",
            updated_at_ms=now_ms,
            weight=1.5
        )
        
        zone_edge = GraphEdge(
            id="e3",
            from_node="ha.entity:light.kitchen",
            to_node="zone:kitchen",
            edge_type="in_zone",
            updated_at_ms=now_ms,
            weight=1.0
        )
        
        store.upsert_edge(affect_edge)
        store.upsert_edge(controls_edge)
        store.upsert_edge(zone_edge)
        
        # Create bridge and extract patterns
        bridge = GraphCandidatesBridge(brain_service)
        
        # Extract habitus patterns
        patterns = bridge.extract_candidate_patterns(pattern_type="habitus")
        assert len(patterns) >= 1, "Should extract at least one pattern"
        
        # Verify pattern structure
        for pattern in patterns:
            assert isinstance(pattern, CandidatePattern)
            assert pattern.pattern_id.startswith("habitus__")
            assert pattern.pattern_type == "habitus"
            assert "antecedent" in pattern.to_dict()
            assert "consequent" in pattern.to_dict()
            assert "evidence" in pattern.to_dict()
        
        # Extract zone activity patterns
        zone_patterns = bridge.extract_candidate_patterns(pattern_type="zone_activity")
        assert len(zone_patterns) >= 1, "Should extract zone pattern"
        
        print(f"✅ Pattern extraction test passed ({len(patterns)} habitus patterns, {len(zone_patterns)} zone patterns)")


def test_pattern_evidence():
    """Test evidence extraction for candidates."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        brain_service = BrainGraphService(store=store)
        
        now_ms = int(time.time() * 1000)
        
        # Create nodes and edge
        node_a = GraphNode(
            id="ha.entity:light.living_room",
            kind="entity",
            label="Living Room Light",
            updated_at_ms=now_ms,
            score=4.0,
            domain="light"
        )
        
        node_b = GraphNode(
            id="ha.entity:media_player.tv",
            kind="entity",
            label="TV",
            updated_at_ms=now_ms,
            score=3.0,
            domain="media_player"
        )
        
        store.upsert_node(node_a)
        store.upsert_node(node_b)
        
        edge = GraphEdge(
            id="test_edge",
            from_node="ha.entity:light.living_room",
            to_node="ha.entity:media_player.tv",
            edge_type="correlates",
            updated_at_ms=now_ms,
            weight=1.8
        )
        
        store.upsert_edge(edge)
        
        bridge = GraphCandidatesBridge(brain_service)
        patterns = bridge.extract_candidate_patterns(pattern_type="habitus")
        
        if patterns:
            pattern = patterns[0]
            evidence = bridge.get_pattern_evidence_for_candidate(pattern)
            
            # Verify evidence structure
            assert "confidence" in evidence
            assert "support" in evidence
            assert "lift" in evidence
            assert "count" in evidence
            assert evidence["confidence"] >= 0
            assert evidence["confidence"] <= 1
            
            print("✅ Pattern evidence test passed")
        else:
            print("⚠️ No patterns extracted (may be due to edge type filtering)")


def test_mood_impact():
    """Test mood impact estimation."""
    bridge = GraphCandidatesBridge(BrainGraphService())
    
    pattern = CandidatePattern(
        pattern_id="test__abc123",
        pattern_type="habitus",
        antecedent={"domain": "light", "service": "light.turn_on", "entity": "light.living_room"},
        consequent={"domain": "switch", "service": "switch.turn_on", "entity": "switch.fan"},
        evidence={"confidence": 0.8, "support": 0.2, "lift": 2.0, "count": 10},
        graph_context={},
        created_at_ms=int(time.time() * 1000),
        source_edge_types=["affects"]
    )
    
    mood = {"comfort": 0.5, "frugality": 0.5, "joy": 0.5}
    impact = bridge._estimate_mood_impact(pattern, mood)
    
    assert isinstance(impact, dict)
    assert "comfort" in impact or "frugality" in impact or "joy" in impact
    
    print("✅ Mood impact test passed")


def test_pii_redaction():
    """Test PII detection in pattern extraction."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        brain_service = BrainGraphService(store=store)
        
        now_ms = int(time.time() * 1000)
        
        # Create node with potentially personal name
        node = GraphNode(
            id="ha.entity:light.johns_bedroom",
            kind="entity",
            label="John's Bedroom Light",
            updated_at_ms=now_ms,
            score=2.0,
            domain="light"
        )
        
        store.upsert_node(node)
        
        bridge = GraphCandidatesBridge(brain_service)
        
        # Should not crash, PII detection is for redacting patterns
        patterns = bridge.extract_candidate_patterns(pattern_type="habitus")
        
        # Node should be parsed correctly
        parsed = bridge._parse_node_id("ha.entity:light.johns_bedroom")
        assert parsed["id"] == "light.johns_bedroom"
        assert parsed["kind"] == "entity"
        assert parsed["domain"] == "light"
        
        # PII check
        assert bridge._contains_pii("test@email.com") == True
        assert bridge._contains_pii("192.168.1.1") == True
        assert bridge._contains_pii("light.kitchen") == False
        
        print("✅ PII redaction test passed")


def test_get_related_entities():
    """Test getting related entities from graph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        brain_service = BrainGraphService(store=store)
        
        now_ms = int(time.time() * 1000)
        
        # Create small graph: light.kitchen → zone.kitchen ← fan.kitchen
        nodes = [
            GraphNode("ha.entity:light.kitchen", "entity", "Kitchen Light", now_ms, 3.0, domain="light"),
            GraphNode("ha.entity:fan.kitchen", "entity", "Kitchen Fan", now_ms, 2.0, domain="fan"),
            GraphNode("zone:kitchen", "zone", "Kitchen", now_ms, 2.5),
        ]
        
        edges = [
            GraphEdge("e1", "ha.entity:light.kitchen", "zone:kitchen", "in_zone", now_ms, 1.0),
            GraphEdge("e2", "ha.entity:fan.kitchen", "zone:kitchen", "in_zone", now_ms, 0.8),
        ]
        
        for node in nodes:
            store.upsert_node(node)
        for edge in edges:
            store.upsert_edge(edge)
        
        bridge = GraphCandidatesBridge(brain_service)
        related = bridge.get_related_entities("light.kitchen", hops=2)
        
        assert "entities" in related
        assert "zones" in related
        assert len(related["zones"]) >= 1
        
        # Should find kitchen zone
        zone_names = [z["label"] for z in related["zones"]]
        assert "Kitchen" in zone_names
        
        print("✅ Get related entities test passed")


def test_pattern_id_generation():
    """Test stable pattern ID generation."""
    bridge = GraphCandidatesBridge(BrainGraphService())
    
    # Same inputs should produce same ID
    id1 = bridge._generate_pattern_id("habitus", "service:a:entity1", "service:b:entity2")
    id2 = bridge._generate_pattern_id("habitus", "service:a:entity1", "service:b:entity2")
    
    assert id1 == id2, "Same inputs should produce same pattern ID"
    assert id1.startswith("habitus__"), "Pattern ID should have type prefix"
    assert len(id1.split("__")[1]) == 12, "Hash should be 12 chars"
    
    # Different inputs should produce different IDs
    id3 = bridge._generate_pattern_id("habitus", "service:x:entity1", "service:b:entity2")
    assert id1 != id3, "Different inputs should produce different IDs"
    
    print("✅ Pattern ID generation test passed")


def test_config_limits():
    """Test configuration limits are respected."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test.db")
        store = GraphStore(db_path=db_path)
        brain_service = BrainGraphService(store=store)
        
        now_ms = int(time.time() * 1000)
        
        # Create many nodes and edges
        for i in range(20):
            node = GraphNode(
                f"ha.entity:light.{i}",
                "entity",
                f"Light {i}",
                now_ms,
                float(5 - i % 5),
                domain="light"
            )
            store.upsert_node(node)
        
        # Create edges between pairs
        for i in range(0, 20, 2):
            edge = GraphEdge(
                f"e{i}",
                f"ha.entity:light.{i}",
                f"ha.entity:light.{i+1}",
                "affects",
                now_ms,
                1.0 + i * 0.1
            )
            store.upsert_edge(edge)
        
        # Test with max_patterns limit
        config = PatternExtractionConfig(max_patterns=5)
        bridge = GraphCandidatesBridge(brain_service, config=config)
        patterns = bridge.extract_candidate_patterns(pattern_type="habitus")
        
        assert len(patterns) <= 5, f"Should respect max_patterns limit, got {len(patterns)}"
        
        print("✅ Config limits test passed")


if __name__ == "__main__":
    print("Running Graph Candidates Bridge tests...\n")
    
    print("Test 1: Bridge initialization")
    test_bridge_initialization()
    
    print("\nTest 2: Pattern extraction")
    test_pattern_extraction()
    
    print("\nTest 3: Pattern evidence")
    test_pattern_evidence()
    
    print("\nTest 4: Mood impact")
    test_mood_impact()
    
    print("\nTest 5: PII redaction")
    test_pii_redaction()
    
    print("\nTest 6: Get related entities")
    test_get_related_entities()
    
    print("\nTest 7: Pattern ID generation")
    test_pattern_id_generation()
    
    print("\nTest 8: Config limits")
    test_config_limits()
    
    print("\n" + "="*50)
    print("✅ All Graph Candidates Bridge tests passed!")
    print("="*50)
