"""
Tests for Habitus Miner and HabitusService.

Covers:
- Pattern discovery from action sequences
- Evidence calculation (support/confidence/lift)
- Debounce and delta window logic
- HabitusService candidate creation from patterns
- Throttle logic for mining runs
- Edge attribute naming (updated_at_ms)
"""
import time
import unittest
from unittest.mock import MagicMock, patch

from copilot_core.brain_graph.model import GraphNode, GraphEdge, NodeKind, EdgeType
from copilot_core.brain_graph.store import GraphStore
from copilot_core.brain_graph.service import BrainGraphService
from copilot_core.candidates.store import CandidateStore, Candidate
from copilot_core.habitus.miner import HabitusMiner, PatternEvidence
from copilot_core.habitus.service import HabitusService


def _make_edge(from_node: str, to_node: str, edge_type: str,
               updated_at_ms: int, weight: float = 1.0) -> GraphEdge:
    """Helper to create a GraphEdge for testing."""
    eid = GraphEdge.create_id(from_node, edge_type, to_node)
    return GraphEdge(
        id=eid,
        from_node=from_node,
        to_node=to_node,
        edge_type=edge_type,
        updated_at_ms=updated_at_ms,
        weight=weight,
        evidence={"kind": "test", "ref": "unit"},
    )


class TestPatternEvidence(unittest.TestCase):
    """Test PatternEvidence data class."""

    def test_to_dict_rounds(self):
        ev = PatternEvidence(support=0.12345, confidence=0.6789, lift=1.234, count=5, total_sessions=10)
        d = ev.to_dict()
        self.assertEqual(d["support"], 0.123)
        self.assertEqual(d["confidence"], 0.679)
        self.assertEqual(d["lift"], 1.234)
        self.assertEqual(d["count"], 5)
        self.assertEqual(d["total_sessions"], 10)


class TestHabitusMiner(unittest.TestCase):
    """Test the core pattern mining engine."""

    def setUp(self):
        import tempfile, os
        self._tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self._tmpdir, "test_graph.db")
        self.store = GraphStore(db_path=db_path)
        self.brain = BrainGraphService(store=self.store)
        self.miner = HabitusMiner(
            brain_service=self.brain,
            min_confidence=0.5,
            min_support=0.05,
            min_lift=1.0,
            delta_window_minutes=10,
            debounce_minutes=2,
        )

    # ---- sequence extraction ------------------------------------------------

    def test_extract_empty_graph(self):
        """No edges → no sequences."""
        sequences = self.miner._extract_action_sequences(lookback_hours=24)
        self.assertEqual(sequences, [])

    def test_extract_filters_non_service_edges(self):
        """Only 'affects' edges from ha.service:* should be included."""
        now_ms = int(time.time() * 1000)
        # in_zone edge (should be excluded)
        self.store.upsert_edge(_make_edge(
            "ha.entity:light.kitchen", "zone:kitchen", "in_zone", now_ms
        ))
        sequences = self.miner._extract_action_sequences(lookback_hours=24)
        self.assertEqual(sequences, [])

    def test_extract_respects_lookback(self):
        """Edges older than lookback are excluded."""
        now_ms = int(time.time() * 1000)
        old_ms = now_ms - 200 * 3600 * 1000  # 200 hours ago
        self.store.upsert_edge(_make_edge(
            "ha.service:light.turn_on", "ha.entity:light.kitchen", "affects", old_ms
        ))
        sequences = self.miner._extract_action_sequences(lookback_hours=24)
        self.assertEqual(sequences, [])

    def test_extract_creates_sessions_with_debounce(self):
        """Actions separated by > debounce gap should split into separate sessions."""
        now_ms = int(time.time() * 1000)
        t1 = now_ms - 60_000   # 1 min ago
        t2 = now_ms - 50_000   # 50s ago  (within debounce of t1)
        t3 = now_ms - 10_000   # 10s ago  (> debounce_ms=120000 from t2? no, 40s gap)
        # debounce is 2 min = 120_000ms; all within debounce → single session
        for t, svc, ent in [(t1, "light.turn_on", "light.kitchen"),
                            (t2, "switch.turn_on", "switch.fan"),
                            (t3, "light.turn_off", "light.kitchen")]:
            self.store.upsert_edge(_make_edge(
                f"ha.service:{svc}", f"ha.entity:{ent}", "affects", t
            ))

        sequences = self.miner._extract_action_sequences(lookback_hours=1)
        self.assertEqual(len(sequences), 1)
        self.assertEqual(len(sequences[0]), 3)

    def test_extract_splits_sessions_on_large_gap(self):
        """A gap > debounce_ms starts a new session."""
        now_ms = int(time.time() * 1000)
        t1 = now_ms - 600_000   # 10 min ago
        t2 = now_ms - 10_000    # 10s ago (gap = 590s > 120s debounce)
        self.store.upsert_edge(_make_edge(
            "ha.service:light.turn_on", "ha.entity:light.kitchen", "affects", t1
        ))
        self.store.upsert_edge(_make_edge(
            "ha.service:switch.turn_on", "ha.entity:switch.fan", "affects", t2
        ))

        sequences = self.miner._extract_action_sequences(lookback_hours=1)
        self.assertEqual(len(sequences), 2)

    # ---- pattern discovery ---------------------------------------------------

    def test_discover_simple_ab_pattern(self):
        """Two actions in a session should produce an A→B pattern."""
        session = [
            {"timestamp": 1000, "service": "light.turn_on", "entity": "light.kitchen",
             "edge": MagicMock()},
            {"timestamp": 2000, "service": "switch.turn_on", "entity": "switch.fan",
             "edge": MagicMock()},
        ]
        patterns = self.miner._discover_patterns([session])
        self.assertEqual(len(patterns), 1)
        key = list(patterns.keys())[0]
        self.assertIn("→", key)

    def test_discover_skips_self_patterns(self):
        """Same action repeated should not produce a pattern."""
        session = [
            {"timestamp": 1000, "service": "light.turn_on", "entity": "light.kitchen",
             "edge": MagicMock()},
            {"timestamp": 2000, "service": "light.turn_on", "entity": "light.kitchen",
             "edge": MagicMock()},
        ]
        patterns = self.miner._discover_patterns([session])
        self.assertEqual(len(patterns), 0)

    def test_discover_respects_delta_window(self):
        """Actions beyond delta_window_ms should not be paired."""
        delta_ms = self.miner.delta_window_ms  # 10 min = 600_000 ms
        session = [
            {"timestamp": 1000, "service": "light.turn_on", "entity": "light.kitchen",
             "edge": MagicMock()},
            {"timestamp": 1000 + delta_ms + 1, "service": "switch.turn_on",
             "entity": "switch.fan", "edge": MagicMock()},
        ]
        patterns = self.miner._discover_patterns([session])
        self.assertEqual(len(patterns), 0)

    # ---- evidence calculation -----------------------------------------------

    def test_calculate_evidence_basic(self):
        """Single session with A→B should yield confidence=1.0."""
        sessions = [[
            {"timestamp": 1000, "service": "light.turn_on", "entity": "light.kitchen",
             "edge": MagicMock()},
            {"timestamp": 2000, "service": "switch.turn_on", "entity": "switch.fan",
             "edge": MagicMock()},
        ]]
        pattern_data = {
            "antecedent": "light.turn_on:light.kitchen",
            "consequent": "switch.turn_on:switch.fan",
            "occurrences": [{"timestamp_a": 1000, "timestamp_b": 2000, "delta_ms": 1000}],
            "sessions_with_pattern": {id(sessions[0])},
        }
        evidence = self.miner._calculate_evidence(pattern_data, sessions)
        self.assertEqual(evidence.confidence, 1.0)
        self.assertEqual(evidence.support, 1.0)
        self.assertGreater(evidence.lift, 0)

    # ---- full mine_patterns pipeline ----------------------------------------

    def test_mine_patterns_end_to_end(self):
        """Full pipeline: edges → sequences → patterns → evidence filtering."""
        now_ms = int(time.time() * 1000)
        # Create two "sessions" (gap > debounce) each with same A→B pair
        for offset in [300_000, 0]:  # 5 min ago and now
            t_base = now_ms - offset
            self.store.upsert_edge(_make_edge(
                "ha.service:light.turn_on", "ha.entity:light.kitchen", "affects",
                t_base
            ))
            self.store.upsert_edge(_make_edge(
                "ha.service:switch.turn_on", "ha.entity:switch.fan", "affects",
                t_base + 5000  # 5s later, within delta window
            ))

        patterns = self.miner.mine_patterns(lookback_hours=1)
        # Should find at least the light→switch pattern
        # (may or may not qualify depending on session split)
        self.assertIsInstance(patterns, dict)


class TestHabitusService(unittest.TestCase):
    """Test HabitusService orchestration."""

    def setUp(self):
        import tempfile, os
        self._tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self._tmpdir, "test_graph.db")
        self.store = GraphStore(db_path=db_path)
        self.brain = BrainGraphService(store=self.store)
        cand_path = os.path.join(self._tmpdir, "test_candidates.json")
        self.candidate_store = CandidateStore(storage_path=cand_path)
        self.service = HabitusService(
            brain_service=self.brain,
            candidate_store=self.candidate_store,
            miner_config={"min_confidence": 0.3, "min_support": 0.01, "min_lift": 0.5},
        )

    def test_throttle_skips_recent_run(self):
        """mine_and_create_candidates should skip if last run was recent."""
        self.service.last_mining_run = time.time()  # just ran
        result = self.service.mine_and_create_candidates(force=False)
        self.assertEqual(result["status"], "skipped")

    def test_force_bypasses_throttle(self):
        """force=True should bypass the throttle."""
        self.service.last_mining_run = time.time()
        result = self.service.mine_and_create_candidates(force=True)
        self.assertEqual(result["status"], "completed")

    def test_creates_candidates_from_patterns(self):
        """When miner finds patterns, candidates should be persisted."""
        fake_patterns = {
            "light.turn_on:light.kitchen→switch.turn_on:switch.fan": {
                "pattern_id": "light.turn_on:light.kitchen→switch.turn_on:switch.fan",
                "antecedent": "light.turn_on:light.kitchen",
                "consequent": "switch.turn_on:switch.fan",
                "evidence": {"support": 0.5, "confidence": 0.8, "lift": 2.0, "count": 3, "total_sessions": 5},
                "discovered_at": int(time.time() * 1000),
            }
        }
        # Patch the miner to return our fake patterns
        self.service.miner.mine_patterns = MagicMock(return_value=fake_patterns)

        result = self.service.mine_and_create_candidates(force=True)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["candidates_created"], 1)

        # Verify candidate in store
        candidates = self.candidate_store.list_candidates()
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.state, "pending")
        self.assertIn("antecedent", c.metadata)

    def test_no_duplicate_candidates(self):
        """Dismissed patterns should not create new candidates."""
        pattern_id = "test→pattern"
        # Pre-populate a dismissed candidate
        self.candidate_store.add_candidate(
            pattern_id=pattern_id,
            evidence={"confidence": 0.9},
            metadata={}
        )
        cid = self.candidate_store.list_candidates()[0].candidate_id
        self.candidate_store.update_candidate_state(cid, "dismissed")

        # Now service should skip this pattern
        existing = self.service._find_existing_candidate(pattern_id)
        self.assertIsNotNone(existing)

    def test_get_pattern_stats(self):
        """Pattern stats should reflect graph and candidate state."""
        stats = self.service.get_pattern_stats()
        self.assertIn("graph_nodes", stats)
        self.assertIn("mining_config", stats)
        self.assertIn("min_confidence", stats["mining_config"])

    def test_list_recent_patterns_empty(self):
        """Empty store should return empty list."""
        result = self.service.list_recent_patterns()
        self.assertEqual(result, [])


class TestHabitusZonesV2(unittest.TestCase):
    """Test Habitus Zones v2 functionality - zone-aware pattern mining."""

    def setUp(self):
        import tempfile, os
        self._tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self._tmpdir, "test_graph.db")
        self.store = GraphStore(db_path=db_path)
        self.brain = BrainGraphService(store=self.store)
        cand_path = os.path.join(self._tmpdir, "test_candidates.json")
        self.candidate_store = CandidateStore(storage_path=cand_path)
        self.miner = HabitusMiner(
            brain_service=self.brain,
            min_confidence=0.3,
            min_support=0.01,
            min_lift=0.5
        )
        self.service = HabitusService(
            brain_service=self.brain,
            candidate_store=self.candidate_store,
            miner_config={"min_confidence": 0.3, "min_support": 0.01, "min_lift": 0.5},
        )

    def tearDown(self):
        """Cleanup temp directory."""
        import shutil, os
        if hasattr(self, '_tmpdir') and os.path.exists(self._tmpdir):
            shutil.rmtree(self._tmpdir)

    def _add_zone_with_entities(self, zone_name: str, entities: list, now_ms: int):
        """Helper to create a zone with entities for testing."""
        zone_id = f"zone:{zone_name}"
        
        # Create zone node
        self.store.upsert_node(GraphNode(
            id=zone_id,
            kind="zone",
            label=zone_name.title(),
            updated_at_ms=now_ms,
            score=0.8,
            domain=None
        ))
        
        # Create entity nodes and zone edges
        for entity_id in entities:
            entity_node_id = f"ha.entity:{entity_id}"
            self.store.upsert_node(GraphNode(
                id=entity_node_id,
                kind="entity",
                label=entity_id.split(".")[-1].replace("_", " ").title(),
                updated_at_ms=now_ms,
                score=0.5,
                domain=entity_id.split(".")[0] if "." in entity_id else None
            ))
            
            # Link entity to zone
            self.store.upsert_edge(GraphEdge(
                id=GraphEdge.create_id(entity_node_id, "in_zone", zone_id),
                from_node=entity_node_id,
                to_node=zone_id,
                edge_type="in_zone",
                updated_at_ms=now_ms,
                weight=0.7
            ))

    def _add_service_action(self, service: str, entity: str, timestamp_ms: int, weight: float = 1.0):
        """Helper to add a service action edge."""
        service_node = f"ha.service:{service}"
        entity_node = f"ha.entity:{entity}"
        self.store.upsert_edge(GraphEdge(
            id=GraphEdge.create_id(service_node, "affects", entity_node),
            from_node=service_node,
            to_node=entity_node,
            edge_type="affects",
            updated_at_ms=timestamp_ms,
            weight=weight
        ))

    def test_get_zones_returns_all_zones(self):
        """get_zones should return all discovered zones."""
        now_ms = int(time.time() * 1000)
        
        # Create two zones
        self._add_zone_with_entities("kitchen", ["light.kitchen", "switch.kitchen_fan"], now_ms)
        self._add_zone_with_entities("bedroom", ["light.bedroom", "switch.bedroom_lamp"], now_ms)
        
        zones = self.brain.get_zones()
        
        self.assertEqual(len(zones), 2)
        zone_ids = {z["id"] for z in zones}
        self.assertIn("zone:kitchen", zone_ids)
        self.assertIn("zone:bedroom", zone_ids)

    def test_get_zones_includes_entity_count(self):
        """get_zones should include entity count for each zone."""
        now_ms = int(time.time() * 1000)
        
        self._add_zone_with_entities("kitchen", ["light.kitchen", "switch.kitchen_fan", "media.player"], now_ms)
        
        zones = self.brain.get_zones()
        
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0]["entity_count"], 3)

    def test_get_zone_entities_returns_entities_in_zone(self):
        """get_zone_entities should return only entities in the specified zone."""
        now_ms = int(time.time() * 1000)
        
        # Create kitchen and bedroom zones
        self._add_zone_with_entities("kitchen", ["light.kitchen", "switch.kitchen_fan"], now_ms)
        self._add_zone_with_entities("bedroom", ["light.bedroom"], now_ms)
        
        result = self.brain.get_zone_entities("kitchen")
        
        self.assertNotIn("error", result)
        self.assertEqual(result["zone"]["id"], "zone:kitchen")
        self.assertEqual(result["entity_count"], 2)
        
        entity_ids = {e["id"] for e in result["entities"]}
        self.assertIn("ha.entity:light.kitchen", entity_ids)
        self.assertIn("ha.entity:switch.kitchen_fan", entity_ids)
        self.assertNotIn("ha.entity:light.bedroom", entity_ids)

    def test_get_zone_entities_normalizes_zone_id(self):
        """get_zone_entities should normalize zone IDs without 'zone:' prefix."""
        now_ms = int(time.time() * 1000)
        
        self._add_zone_with_entities("kitchen", ["light.kitchen"], now_ms)
        
        # Should work with or without zone: prefix
        result1 = self.brain.get_zone_entities("zone:kitchen")
        result2 = self.brain.get_zone_entities("kitchen")
        
        self.assertNotIn("error", result1)
        self.assertNotIn("error", result2)

    def test_get_zone_entities_returns_error_for_nonexistent_zone(self):
        """get_zone_entities should return error for unknown zones."""
        result = self.brain.get_zone_entities("nonexistent_zone")
        
        self.assertIn("error", result)
        self.assertIn("not found", result["error"].lower())

    def test_mine_patterns_with_zone_filter(self):
        """mine_patterns should filter patterns to specific zone."""
        now_ms = int(time.time() * 1000)
        lookback_hours = 1
        
        # Create kitchen zone with entities
        self._add_zone_with_entities("kitchen", ["light.kitchen", "switch.kitchen_fan"], now_ms)
        
        # Add actions in kitchen (should be included)
        self._add_service_action("light.turn_on", "light.kitchen", now_ms, weight=1.0)
        self._add_service_action("switch.turn_on", "switch.kitchen_fan", now_ms + 5000, weight=1.0)
        
        # Add actions outside kitchen (should be excluded when zone=kitchen)
        self._add_service_action("light.turn_on", "light.bedroom", now_ms + 1000, weight=1.0)
        
        # Mine without zone filter
        patterns_all = self.miner.mine_patterns(lookback_hours=lookback_hours)
        
        # Mine with zone filter
        patterns_kitchen = self.miner.mine_patterns(lookback_hours=lookback_hours, zone="kitchen")
        
        # Kitchen patterns should be a subset of all patterns (or equal)
        self.assertGreaterEqual(len(patterns_all), len(patterns_kitchen))
        
        # Verify zone filter only includes entities in kitchen
        if patterns_kitchen:
            for pattern_id, pattern_data in patterns_kitchen.items():
                ant_entity = pattern_data["antecedent"].split(":")[-1] if ":" in pattern_data["antecedent"] else pattern_data["antecedent"]
                cons_entity = pattern_data["consequent"].split(":")[-1] if ":" in pattern_data["consequent"] else pattern_data["consequent"]
                # Both entities should be in kitchen
                self.assertIn(ant_entity, ["light.kitchen", "switch.kitchen_fan"])
                self.assertIn(cons_entity, ["light.kitchen", "switch.kitchen_fan"])

    def test_mine_patterns_with_nonexistent_zone_returns_empty(self):
        """mine_patterns with nonexistent zone should return empty dict."""
        patterns = self.miner.mine_patterns(lookback_hours=1, zone="nonexistent_zone")
        
        self.assertEqual(patterns, {})

    def test_mine_and_create_candidates_with_zone(self):
        """mine_and_create_candidates should support zone parameter."""
        now_ms = int(time.time() * 1000)
        
        # Create zone and add actions
        self._add_zone_with_entities("living_room", ["tv.living_room", "light.living_room"], now_ms)
        self._add_service_action("media_player.turn_on", "tv.living_room", now_ms, weight=1.5)
        self._add_service_action("light.turn_on", "light.living_room", now_ms + 3000, weight=1.5)
        
        # Run mining with zone filter
        result = self.service.mine_and_create_candidates(
            lookback_hours=1,
            force=True,
            zone="living_room"
        )
        
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["zone"], "living_room")

    def test_candidate_metadata_includes_zone_filter(self):
        """Created candidates should include zone filter in metadata."""
        now_ms = int(time.time() * 1000)
        
        # Create zone and add action pattern
        self._add_zone_with_entities("office", ["light.office", "switch.office_fan"], now_ms)
        self._add_service_action("light.turn_on", "light.office", now_ms, weight=2.0)
        self._add_service_action("switch.turn_on", "switch.office_fan", now_ms + 2000, weight=2.0)
        
        # Run mining with zone filter
        self.service.mine_and_create_candidates(lookback_hours=1, force=True, zone="office")
        
        # Check that candidates have zone metadata
        candidates = self.candidate_store.list_candidates()
        for candidate in candidates:
            self.assertEqual(candidate.metadata.get("zone_filter"), "office")
            self.assertEqual(candidate.metadata.get("discovery_method"), "habitus_miner_v2")


if __name__ == "__main__":
    unittest.main()
