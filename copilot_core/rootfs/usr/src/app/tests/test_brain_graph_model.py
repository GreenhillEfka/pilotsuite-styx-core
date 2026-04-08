#!/usr/bin/env python3
"""
Tests for brain graph model classes.
"""

import time
import tempfile
from copilot_core.brain_graph.model import GraphNode, GraphEdge


def test_node_creation():
    """Test basic node creation and validation."""
    now_ms = int(time.time() * 1000)
    
    node = GraphNode(
        id="ha.entity:light.kitchen",
        kind="entity",
        label="Kitchen Light",
        updated_at_ms=now_ms,
        score=2.5,
        domain="light",
        tags=["room:kitchen", "type:main"],
        meta={"brightness": 100, "color": "warm"}
    )
    
    assert node.id == "ha.entity:light.kitchen"
    assert node.kind == "entity"
    assert node.label == "Kitchen Light"
    assert node.domain == "light"
    assert len(node.tags) == 2
    assert "brightness" in node.meta
    

def test_node_pii_redaction():
    """Test PII redaction in node data."""
    node = GraphNode(
        id="test:node",
        kind="entity", 
        label="Contact test@example.com at 555-123-4567",
        updated_at_ms=int(time.time() * 1000),
        score=1.0,
        tags=["email:user@domain.com", "phone:123-456-7890"]
    )
    
    # PII should be redacted
    assert "[REDACTED]" in node.label
    assert "test@example.com" not in node.label
    assert "555-123-4567" not in node.label
    
    # Tags should also be redacted
    redacted_tags = [tag for tag in node.tags if "[REDACTED]" in tag]
    assert len(redacted_tags) == 2


def test_node_meta_bounds():
    """Test metadata size limits."""
    large_meta = {f"key_{i}": f"value_{i}" * 100 for i in range(20)}
    
    node = GraphNode(
        id="test:bounded",
        kind="entity",
        label="Test Node",
        updated_at_ms=int(time.time() * 1000),
        score=1.0,
        meta=large_meta
    )
    
    # Should be limited to 10 keys
    assert len(node.meta) <= 10
    
    # Total JSON size should be under 2KB
    import json
    assert len(json.dumps(node.meta)) <= 2048


def test_node_effective_score():
    """Test score decay calculation."""
    now_ms = int(time.time() * 1000)
    past_ms = now_ms - (24 * 3600 * 1000)  # 24 hours ago
    
    node = GraphNode(
        id="test:decay",
        kind="entity",
        label="Test",
        updated_at_ms=past_ms,
        score=4.0
    )
    
    # After 24 hours with 24h half-life, should be ~2.0
    effective = node.effective_score(now_ms, half_life_hours=24.0)
    assert 1.8 < effective < 2.2


def test_edge_creation():
    """Test basic edge creation."""
    now_ms = int(time.time() * 1000)
    
    edge = GraphEdge(
        id="test_edge",
        from_node="node1",
        to_node="node2", 
        edge_type="controls",
        updated_at_ms=now_ms,
        weight=1.5,
        evidence={"kind": "rule", "ref": "automation.test"},
        meta={"confidence": 0.8}
    )
    
    assert edge.from_node == "node1"
    assert edge.to_node == "node2"
    assert edge.edge_type == "controls"
    assert edge.evidence["kind"] == "rule"


def test_edge_id_generation():
    """Test stable edge ID generation."""
    id1 = GraphEdge.create_id("node1", "controls", "node2")
    id2 = GraphEdge.create_id("node1", "controls", "node2")
    id3 = GraphEdge.create_id("node2", "controls", "node1")
    
    # Same inputs should produce same ID
    assert id1 == id2
    
    # Different inputs should produce different ID
    assert id1 != id3
    
    # Should have expected format
    assert id1.startswith("e:")
    assert len(id1) == 18  # "e:" + 16 hex chars


def test_edge_evidence_sanitization():
    """Test edge evidence sanitization."""
    edge = GraphEdge(
        id="test",
        from_node="node1",
        to_node="node2",
        edge_type="correlates", 
        updated_at_ms=int(time.time() * 1000),
        weight=1.0,
        evidence={
            "kind": "event",
            "ref": "test_ref",
            "invalid_key": "should_be_removed",
            "summary": "contact admin@test.com"
        }
    )
    
    # Only allowed keys should remain
    assert "kind" in edge.evidence
    assert "ref" in edge.evidence
    assert "summary" in edge.evidence
    assert "invalid_key" not in edge.evidence
    
    # PII should be redacted from summary
    assert "[REDACTED]" in edge.evidence["summary"]
    assert "admin@test.com" not in edge.evidence["summary"]


def test_edge_effective_weight():
    """Test weight decay calculation.""" 
    now_ms = int(time.time() * 1000)
    past_ms = now_ms - (12 * 3600 * 1000)  # 12 hours ago
    
    edge = GraphEdge(
        id="test_decay",
        from_node="node1",
        to_node="node2",
        edge_type="correlates",
        updated_at_ms=past_ms,
        weight=2.0
    )
    
    # After 12 hours with 12h half-life, should be ~1.0
    effective = edge.effective_weight(now_ms, half_life_hours=12.0)
    assert 0.9 < effective < 1.1


if __name__ == "__main__":
    print("Testing GraphNode creation...")
    test_node_creation()
    
    print("Testing PII redaction...")
    test_node_pii_redaction()
    
    print("Testing metadata bounds...")
    test_node_meta_bounds()
    
    print("Testing score decay...")
    test_node_effective_score()
    
    print("Testing GraphEdge creation...")
    test_edge_creation()
    
    print("Testing edge ID generation...")
    test_edge_id_generation()
    
    print("Testing evidence sanitization...")
    test_edge_evidence_sanitization()
    
    print("Testing weight decay...")
    test_edge_effective_weight()
    
    print("✅ All brain graph model tests passed!")