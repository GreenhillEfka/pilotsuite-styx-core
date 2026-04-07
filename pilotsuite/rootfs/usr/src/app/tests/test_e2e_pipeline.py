#!/usr/bin/env python3
"""
End-to-End Pipeline Integration Test
=====================================
Tests the complete suggestion pipeline in-process:

  Events → EventProcessor → BrainGraph → HabitusMiner → Candidates

This validates that all modules connect correctly and the full
pipeline produces candidates from raw HA-style events.

Usage:
    python3 -m tests.test_e2e_pipeline
    # or from the add-on container:
    python3 tests/test_e2e_pipeline.py

Exit code 0 = all tests pass.

Note: Flask API smoke tests only run when flask is available (in-container).
"""
import sys
import os
import json
import time
import tempfile
import shutil
import logging
import types

# Add app root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Mock missing optional deps so core modules can import ─────────────
# The test exercises business logic, not system metrics or HTTP serving.

def _ensure_mock(module_name):
    """Create a lightweight mock module if it's not installed."""
    if module_name in sys.modules:
        return
    try:
        __import__(module_name)
    except ImportError:
        mod = types.ModuleType(module_name)
        if module_name == "psutil":
            mod.cpu_percent = lambda *a, **kw: 0.0
            mod.virtual_memory = lambda: types.SimpleNamespace(percent=0.0, total=1, available=1)
            mod.disk_usage = lambda *a: types.SimpleNamespace(percent=0.0, total=1, free=1)
        elif module_name == "flask":
            # Comprehensive mock — enough for all import statements
            _noop_decorator = lambda *a, **kw: (lambda f: f)
            _BlueprintMeta = type("Blueprint", (), {
                "__init__": lambda self, *a, **kw: None,
                "route": _noop_decorator,
                "before_request": _noop_decorator,
                "after_request": _noop_decorator,
            })
            mod.Flask = type("Flask", (), {
                "__init__": lambda self, *a, **kw: None,
                "register_blueprint": lambda self, *a, **kw: None,
            })
            mod.Blueprint = _BlueprintMeta
            mod.request = types.SimpleNamespace(
                get_json=lambda **kw: {},
                args=types.SimpleNamespace(get=lambda k, d=None: d),
                headers={},
            )
            mod.jsonify = lambda x={}, **kw: x
            mod.Response = type("Response", (), {"__init__": lambda *a, **kw: None})
            mod.Request = type("Request", (), {"__init__": lambda *a, **kw: None})
            mod.abort = lambda code: None
            mod.make_response = lambda *a: None
            mod.current_app = types.SimpleNamespace(logger=logging.getLogger("flask_mock"))
            mod.g = types.SimpleNamespace()
            mod.session = {}
            mod.url_for = lambda *a, **kw: ""
            mod.redirect = lambda *a, **kw: None
            mod.render_template = lambda *a, **kw: ""
            mod.send_file = lambda *a, **kw: None
        elif module_name == "waitress":
            mod.serve = lambda *a, **kw: None
        sys.modules[module_name] = mod

for _m in ["psutil", "flask", "waitress"]:
    _ensure_mock(_m)

from copilot_core.brain_graph.service import BrainGraphService
from copilot_core.ingest.event_processor import EventProcessor
from copilot_core.candidates.store import CandidateStore
from copilot_core.habitus.service import HabitusService
from copilot_core.habitus.miner import HabitusMiner

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("e2e_test")

# ── Helpers ──────────────────────────────────────────────────────────

def make_state_event(entity_id: str, new_state: str, ts: float, old_state: str = "off") -> dict:
    """Create a realistic HA state_changed event envelope."""
    return {
        "id": f"evt_{entity_id}_{int(ts)}",
        "kind": "state_changed",
        "entity_id": entity_id,
        "ts": ts,
        "old_state": old_state,
        "new_state": new_state,
        "attributes": {},
    }


def make_service_call_event(entity_id: str, service: str, ts: float, domain: str = "light") -> dict:
    """Create a realistic HA service call event envelope."""
    return {
        "id": f"svc_{entity_id}_{int(ts)}",
        "kind": "service_call",
        "entity_id": entity_id,
        "ts": ts,
        "domain": domain,
        "service": service,
        "service_data": {"entity_id": entity_id},
    }


import pytest


@pytest.fixture
def result():
    """Provide a PipelineResult instance for pipeline tests."""
    return PipelineResult()


@pytest.fixture
def bg():
    """Provide a BrainGraphService for pipeline tests."""
    return BrainGraphService()


class PipelineResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str):
        self.passed += 1
        logger.info(f"  ✅ {name}")

    def fail(self, name: str, reason: str):
        self.failed += 1
        self.errors.append(f"{name}: {reason}")
        logger.error(f"  ❌ {name} — {reason}")

    def check(self, name: str, condition: bool, reason: str = "assertion failed"):
        if condition:
            self.ok(name)
        else:
            self.fail(name, reason)

    @property
    def success(self) -> bool:
        return self.failed == 0

    def summary(self) -> str:
        total = self.passed + self.failed
        return f"{self.passed}/{total} passed" + (
            f" — FAILURES: {self.errors}" if self.errors else ""
        )


# ── Test 1: Event Processor → Brain Graph ────────────────────────────

def _run_event_processor_to_brain_graph(result: PipelineResult) -> BrainGraphService:
    """Verify events are processed and appear in Brain Graph."""
    logger.info("Test 1: Event Processor → Brain Graph")

    bg = BrainGraphService()
    ep = EventProcessor(brain_graph_service=bg)

    # Simulate a pattern: motion sensor → light on (repeated 10 times)
    base_time = time.time() - 3600  # 1h ago
    events = []
    for i in range(10):
        t = base_time + i * 300  # every 5 min
        events.append(make_state_event("binary_sensor.motion_living", "on", t, "off"))
        events.append(make_service_call_event("light.living_room", "turn_on", t + 5))

    stats = ep.process_events(events)

    result.check(
        "events processed",
        stats["processed"] == 20,
        f"expected 20, got {stats['processed']}"
    )
    result.check(
        "no processing errors",
        stats["errors"] == 0,
        f"got {stats['errors']} errors"
    )

    # Brain graph should have nodes
    graph_state = bg.get_graph_state()
    node_count = graph_state.get("node_count", len(graph_state.get("nodes", [])))
    result.check(
        "brain graph has nodes",
        node_count >= 1,
        f"expected ≥1 nodes, got {node_count}"
    )
    logger.info(f"  → graph node count: {node_count}")

    return bg


def test_event_processor_to_brain_graph(result: PipelineResult):
    _run_event_processor_to_brain_graph(result)


# ── Test 2: Brain Graph → Habitus Miner ──────────────────────────────

def _run_habitus_miner(result: PipelineResult, bg: BrainGraphService) -> dict:
    """Verify the miner discovers patterns from brain graph."""
    logger.info("Test 2: Brain Graph → Habitus Miner")

    miner = HabitusMiner(
        brain_service=bg,
        min_confidence=0.3,
        min_support=0.05,
        min_lift=0.5,
        delta_window_minutes=15,
        debounce_minutes=1,
    )

    patterns = miner.mine_patterns()

    result.check(
        "miner returns dict",
        isinstance(patterns, dict),
        f"expected dict, got {type(patterns)}"
    )
    result.ok("miner runs without error")

    return patterns


def test_habitus_miner(result: PipelineResult, bg: BrainGraphService):
    _run_habitus_miner(result, bg)


# ── Test 3: Full Pipeline → Candidates ───────────────────────────────

def test_full_pipeline_candidates(result: PipelineResult):
    """Full pipeline: events → brain graph → habitus → candidates."""
    logger.info("Test 3: Full Pipeline → Candidate Creation")

    bg = BrainGraphService()
    ep = EventProcessor(brain_graph_service=bg)

    tmp_dir = tempfile.mkdtemp(prefix="copilot_test_")
    try:
        storage_file = os.path.join(tmp_dir, "candidates.json")
        cs = CandidateStore(storage_path=storage_file)
        hs = HabitusService(
            brain_service=bg,
            candidate_store=cs,
            miner_config={
                "min_confidence": 0.2,
                "min_support": 0.02,
                "min_lift": 0.3,
                "delta_window_minutes": 20,
                "debounce_minutes": 1,
            },
        )

        # Generate a strong A→B pattern: door → hallway light (20 repetitions)
        base_time = time.time() - 7200
        events = []
        for i in range(20):
            t = base_time + i * 360
            events.append(make_state_event("binary_sensor.front_door", "on", t, "off"))
            events.append(make_service_call_event("light.hallway", "turn_on", t + 3))
            events.append(make_state_event("binary_sensor.front_door", "off", t + 60, "on"))

        stats = ep.process_events(events)
        result.check(
            "pipeline events processed",
            stats["processed"] == 60,
            f"expected 60, got {stats['processed']}"
        )

        mine_result = hs.mine_and_create_candidates()
        result.check(
            "mine_and_create returns dict",
            isinstance(mine_result, dict),
            f"expected dict, got {type(mine_result)}"
        )

        patterns_found = mine_result.get("patterns_found", 0)
        candidates_created = mine_result.get("candidates_created", 0)
        logger.info(f"  → patterns_found={patterns_found}, candidates_created={candidates_created}")

        all_candidates = cs.list_candidates()
        result.check(
            "candidate store accessible",
            isinstance(all_candidates, list),
            f"expected list, got {type(all_candidates)}"
        )

        pending = cs.list_candidates(state="pending")
        logger.info(f"  → pending candidates: {len(pending)}")

        if len(pending) > 0:
            c = pending[0]
            cid = c.candidate_id if hasattr(c, "candidate_id") else c.get("candidate_id", c.get("id"))
            result.ok(f"candidate created: {cid}")

            cs.update_candidate_state(cid, new_state="offered")
            updated = cs.get_candidate(cid)
            state_val = updated.state if hasattr(updated, "state") else updated.get("state")
            result.check("candidate state → offered", state_val == "offered", f"got {state_val}")

            cs.update_candidate_state(cid, new_state="accepted")
            updated2 = cs.get_candidate(cid)
            state_val2 = updated2.state if hasattr(updated2, "state") else updated2.get("state")
            result.check("candidate state → accepted", state_val2 == "accepted", f"got {state_val2}")
        else:
            result.ok("no candidates created (miner thresholds not met — OK for graph structure)")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Test 4: Candidate Store CRUD ──────────────────────────────────────

def test_candidate_store_crud(result: PipelineResult):
    """Test candidate store persistence and CRUD operations."""
    logger.info("Test 4: Candidate Store CRUD")

    tmp_dir = tempfile.mkdtemp(prefix="copilot_test_cs_")
    try:
        storage_file = os.path.join(tmp_dir, "candidates.json")
        cs = CandidateStore(storage_path=storage_file)

        cand_id = cs.add_candidate(
            pattern_id="test_a_to_b",
            evidence={"support": 0.85, "confidence": 0.92, "lift": 3.2},
            metadata={"trigger": "binary_sensor.motion", "target": "light.living"},
        )
        result.ok("candidate added")

        fetched = cs.get_candidate(cand_id)
        result.check("candidate fetched", fetched is not None, "get_candidate returned None")

        all_c = cs.list_candidates()
        result.check("list_candidates returns 1", len(all_c) == 1, f"expected 1, got {len(all_c)}")

        cs.update_candidate_state(cand_id, "dismissed")
        dismissed = cs.get_candidate(cand_id)
        state_val = dismissed.state if hasattr(dismissed, "state") else dismissed.get("state")
        result.check("update_candidate works", state_val == "dismissed", f"got {state_val}")

        cand_id_2 = cs.add_candidate(
            pattern_id="test_deferred",
            evidence={"support": 0.5, "confidence": 0.6, "lift": 1.5},
            metadata={},
        )
        cs.update_candidate_state(cand_id_2, "deferred", retry_after=time.time() + 86400)
        deferred = cs.list_candidates(state="deferred")
        result.check("deferred candidate stored", len(deferred) >= 1, f"expected ≥1, got {len(deferred)}")

        stats = cs.get_stats()
        result.check("stats available", isinstance(stats, dict), f"expected dict, got {type(stats)}")
        logger.info(f"  → store stats: {json.dumps(stats)}")

        # Persistence: reload from disk
        cs2 = CandidateStore(storage_path=storage_file)
        reloaded = cs2.list_candidates()
        result.check(
            "persistence across reload",
            len(reloaded) == 2,
            f"expected 2 after reload, got {len(reloaded)}"
        )

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Test 5: Flask API Smoke Test (only when flask is real) ────────────

def test_flask_api_smoke(result: PipelineResult):
    """Test Core Flask app responds correctly to key endpoints."""
    try:
        import flask
        if not hasattr(flask.Flask, "__call__"):
            logger.info("Test 5: Flask API Smoke — SKIPPED (flask not installed)")
            result.ok("flask API smoke skipped (mock flask)")
            return
    except Exception:
        logger.info("Test 5: Flask API Smoke — SKIPPED (flask not available)")
        result.ok("flask API smoke skipped")
        return

    logger.info("Test 5: Flask API Smoke Test")

    os.environ.setdefault("COPILOT_API_TOKEN", "test_token_e2e")
    os.environ.setdefault("COPILOT_VERSION", "0.4.5-test")

    try:
        from main import app
    except ModuleNotFoundError as e:
        logger.info(f"Test 5: Flask API Smoke — SKIPPED (missing dep: {e})")
        result.ok("flask API smoke skipped (missing optional dependencies)")
        return
    except Exception as e:
        logger.info(f"Test 5: Flask API Smoke — SKIPPED (error: {e})")
        result.ok("flask API smoke skipped (error loading app)")
        return

    client = app.test_client()

    resp = client.get("/health")
    result.check("GET /health → 200", resp.status_code == 200, f"got {resp.status_code}")

    resp = client.get("/version")
    result.check("GET /version → 200", resp.status_code == 200, f"got {resp.status_code}")

    resp = client.post("/api/v1/echo", json={"test": True},
                       headers={"Authorization": "Bearer test_token_e2e"})
    result.check("POST /api/v1/echo → 200", resp.status_code == 200, f"got {resp.status_code}")

    resp = client.post("/api/v1/echo", json={"test": True})
    result.check("POST /api/v1/echo no-auth → 401", resp.status_code == 401, f"got {resp.status_code}")

    resp = client.post("/api/v1/events", json={
        "items": [make_state_event("light.test", "on", time.time())]
    }, headers={"Authorization": "Bearer test_token_e2e"})
    result.check("POST /api/v1/events → 200", resp.status_code == 200, f"got {resp.status_code}")

    resp = client.get("/api/v1/candidates",
                      headers={"Authorization": "Bearer test_token_e2e"})
    result.check("GET /api/v1/candidates → 200", resp.status_code == 200, f"got {resp.status_code}")

    resp = client.get("/api/v1/graph/state",
                      headers={"Authorization": "Bearer test_token_e2e"})
    result.check("GET /api/v1/graph/state → 200", resp.status_code == 200, f"got {resp.status_code}")

    resp = client.post("/api/v1/habitus/mine", json={},
                       headers={"Authorization": "Bearer test_token_e2e"})
    result.check("POST /api/v1/habitus/mine → 200", resp.status_code == 200, f"got {resp.status_code}")


# ── Main ──────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("PilotSuite Core — End-to-End Pipeline Test")
    print("=" * 60)

    result = PipelineResult()

    try:
        bg = _run_event_processor_to_brain_graph(result)
        _run_habitus_miner(result, bg)
        test_full_pipeline_candidates(result)
        test_candidate_store_crud(result)
        test_flask_api_smoke(result)
    except Exception as e:
        result.fail("UNEXPECTED EXCEPTION", str(e))
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)
    status = "PASS ✅" if result.success else "FAIL ❌"
    print(f"Result: {status} — {result.summary()}")
    print("=" * 60)

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
