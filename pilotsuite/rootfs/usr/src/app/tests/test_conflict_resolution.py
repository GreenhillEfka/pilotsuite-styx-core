"""Tests for Conflict Resolution Engine and API.

Coverage:
- ConflictResolver (unit tests): evaluate, strategies, edge cases
- ConflictState serialization
- API endpoints (integration tests)
- Integration with UserPreferenceStore
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from copilot_core.storage.conflict_resolution import (
    ConflictDetail,
    ConflictResolver,
    ConflictState,
)


# ── Unit Tests: ConflictResolver ─────────────────────────────────────────


class TestConflictResolverInit:
    def test_default_threshold(self):
        r = ConflictResolver()
        assert r.threshold == 0.3

    def test_custom_threshold(self):
        r = ConflictResolver(threshold=0.5)
        assert r.threshold == 0.5

    def test_initial_state_inactive(self):
        r = ConflictResolver()
        assert r.state.active is False
        assert r.state.conflicts == []


class TestSetStrategy:
    def test_set_weighted(self):
        r = ConflictResolver()
        r.set_strategy("weighted")
        assert r._resolution_strategy == "weighted"

    def test_set_compromise(self):
        r = ConflictResolver()
        r.set_strategy("compromise")
        assert r._resolution_strategy == "compromise"

    def test_set_override(self):
        r = ConflictResolver()
        r.set_strategy("override", override_user="alice")
        assert r._resolution_strategy == "override"
        assert r._override_user == "alice"

    def test_invalid_strategy(self):
        r = ConflictResolver()
        with pytest.raises(ValueError, match="Unknown strategy"):
            r.set_strategy("invalid")


class TestEvaluate:
    def test_no_conflict(self):
        r = ConflictResolver()
        moods = {
            "alice": {"comfort": 0.7, "frugality": 0.6, "joy": 0.5},
            "bob": {"comfort": 0.8, "frugality": 0.7, "joy": 0.6},
        }
        state = r.evaluate(moods, {"alice": 0.5, "bob": 0.5})
        assert state.active is False
        assert len(state.conflicts) == 0

    def test_conflict_detected(self):
        r = ConflictResolver()
        moods = {
            "alice": {"comfort": 0.9, "frugality": 0.2, "joy": 0.5},
            "bob": {"comfort": 0.1, "frugality": 0.8, "joy": 0.5},
        }
        state = r.evaluate(moods, {"alice": 0.5, "bob": 0.5})
        assert state.active is True
        assert len(state.conflicts) >= 2  # comfort + frugality diverge

    def test_conflict_users_tracked(self):
        r = ConflictResolver()
        moods = {
            "alice": {"comfort": 1.0, "frugality": 0.0, "joy": 0.5},
            "bob": {"comfort": 0.0, "frugality": 1.0, "joy": 0.5},
        }
        state = r.evaluate(moods, {"alice": 0.5, "bob": 0.5})
        assert "alice" in state.users_involved
        assert "bob" in state.users_involved

    def test_three_users(self):
        r = ConflictResolver()
        moods = {
            "a": {"comfort": 0.9, "frugality": 0.5, "joy": 0.5},
            "b": {"comfort": 0.1, "frugality": 0.5, "joy": 0.5},
            "c": {"comfort": 0.5, "frugality": 0.5, "joy": 0.5},
        }
        state = r.evaluate(moods, {"a": 0.5, "b": 0.5, "c": 0.5})
        assert state.active is True
        # a-b should conflict on comfort
        axes = [c.axis for c in state.conflicts]
        assert "comfort" in axes

    def test_empty_moods(self):
        r = ConflictResolver()
        state = r.evaluate({}, {})
        assert state.active is False
        assert state.resolved_mood == {"comfort": 0.5, "frugality": 0.5, "joy": 0.5}

    def test_single_user(self):
        r = ConflictResolver()
        moods = {"alice": {"comfort": 0.8, "frugality": 0.3, "joy": 0.6}}
        state = r.evaluate(moods, {"alice": 0.7})
        assert state.active is False
        assert len(state.users_involved) == 1


class TestResolutionStrategies:
    def _moods(self):
        return {
            "alice": {"comfort": 0.9, "frugality": 0.2, "joy": 0.5},
            "bob": {"comfort": 0.1, "frugality": 0.8, "joy": 0.5},
        }

    def test_weighted_resolution(self):
        r = ConflictResolver()
        r.set_strategy("weighted")
        state = r.evaluate(self._moods(), {"alice": 0.8, "bob": 0.2})
        # alice has 80% weight → comfort should be closer to 0.9
        assert state.resolved_mood["comfort"] > 0.6

    def test_compromise_resolution(self):
        r = ConflictResolver()
        r.set_strategy("compromise")
        state = r.evaluate(self._moods(), {"alice": 0.8, "bob": 0.2})
        # Equal average: (0.9+0.1)/2 = 0.5
        assert abs(state.resolved_mood["comfort"] - 0.5) < 0.01

    def test_override_resolution(self):
        r = ConflictResolver()
        r.set_strategy("override", override_user="alice")
        state = r.evaluate(self._moods(), {"alice": 0.5, "bob": 0.5})
        assert state.resolved_mood["comfort"] == 0.9
        assert state.override_user == "alice"

    def test_override_unknown_user_falls_to_weighted(self):
        r = ConflictResolver()
        r.set_strategy("override", override_user="charlie")
        state = r.evaluate(self._moods(), {"alice": 0.5, "bob": 0.5})
        # charlie not in moods → falls through to weighted
        assert "comfort" in state.resolved_mood


class TestConflictState:
    def test_to_dict(self):
        state = ConflictState(
            active=True,
            conflicts=[ConflictDetail("comfort", "a", "b", 0.9, 0.1, 0.8)],
            users_involved=["a", "b"],
            resolution="weighted",
            resolved_mood={"comfort": 0.5, "frugality": 0.5, "joy": 0.5},
        )
        d = state.to_dict()
        assert d["active"] is True
        assert d["conflict_count"] == 1
        assert d["details"][0]["axis"] == "comfort"
        assert d["details"][0]["divergence"] == 0.8


class TestEvaluateFromStore:
    def test_no_store(self):
        r = ConflictResolver()
        state = r.evaluate_from_store()
        assert state.active is False

    def test_single_user_in_store(self):
        mock_user = MagicMock()
        mock_user.user_id = "alice"
        mock_user.preferences = {"mood_weights": {"comfort": 0.8, "frugality": 0.5, "joy": 0.6}}
        mock_user.priority = 0.7

        mock_store = MagicMock()
        mock_store.list_users.return_value = [mock_user]

        r = ConflictResolver(user_preference_store=mock_store)
        state = r.evaluate_from_store()
        assert state.active is False

    def test_two_users_conflict(self):
        u1 = MagicMock()
        u1.user_id = "alice"
        u1.preferences = {"mood_weights": {"comfort": 0.9, "frugality": 0.1, "joy": 0.5}}
        u1.priority = 0.5

        u2 = MagicMock()
        u2.user_id = "bob"
        u2.preferences = {"mood_weights": {"comfort": 0.1, "frugality": 0.9, "joy": 0.5}}
        u2.priority = 0.5

        mock_store = MagicMock()
        mock_store.list_users.return_value = [u1, u2]

        r = ConflictResolver(user_preference_store=mock_store)
        state = r.evaluate_from_store()
        assert state.active is True

    def test_filter_active_ids(self):
        u1 = MagicMock()
        u1.user_id = "alice"
        u1.preferences = {"mood_weights": {"comfort": 0.9, "frugality": 0.1, "joy": 0.5}}
        u1.priority = 0.5

        u2 = MagicMock()
        u2.user_id = "bob"
        u2.preferences = {"mood_weights": {"comfort": 0.1, "frugality": 0.9, "joy": 0.5}}
        u2.priority = 0.5

        mock_store = MagicMock()
        mock_store.list_users.return_value = [u1, u2]

        r = ConflictResolver(user_preference_store=mock_store)
        # Only alice active → no conflict possible
        state = r.evaluate_from_store(active_user_ids=["alice"])
        assert state.active is False


# ── Integration Tests: API Blueprint ─────────────────────────────────────


class TestConflictResolutionAPI:
    @pytest.fixture
    def client(self):
        from flask import Flask
        from copilot_core.api.v1.conflict_resolution import bp
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["COPILOT_SERVICES"] = {
            "conflict_resolver": ConflictResolver(),
        }
        app.register_blueprint(bp)
        with app.test_client() as c:
            yield c

    def test_get_state(self, client):
        resp = client.get("/api/v1/conflicts/state")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["active"] is False

    def test_evaluate_explicit(self, client):
        resp = client.post("/api/v1/conflicts/evaluate", json={
            "user_moods": {
                "alice": {"comfort": 0.9, "frugality": 0.1, "joy": 0.5},
                "bob": {"comfort": 0.1, "frugality": 0.9, "joy": 0.5},
            },
            "user_priorities": {"alice": 0.5, "bob": 0.5},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["active"] is True
        assert data["conflict_count"] >= 2

    def test_set_strategy(self, client):
        resp = client.post("/api/v1/conflicts/strategy", json={"strategy": "compromise"})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_set_invalid_strategy(self, client):
        resp = client.post("/api/v1/conflicts/strategy", json={"strategy": "invalid"})
        assert resp.status_code == 400

    def test_set_strategy_missing(self, client):
        resp = client.post("/api/v1/conflicts/strategy", json={})
        assert resp.status_code == 400

    def test_evaluate_no_body(self, client):
        # No store wired → should warn but not crash
        resp = client.post("/api/v1/conflicts/evaluate", json={})
        assert resp.status_code in (200, 500)

    def test_state_after_evaluate(self, client):
        # Evaluate first
        client.post("/api/v1/conflicts/evaluate", json={
            "user_moods": {
                "a": {"comfort": 0.9, "frugality": 0.1, "joy": 0.5},
                "b": {"comfort": 0.1, "frugality": 0.9, "joy": 0.5},
            },
            "user_priorities": {"a": 0.5, "b": 0.5},
        })
        # State should reflect the evaluation
        resp = client.get("/api/v1/conflicts/state")
        data = resp.get_json()
        assert data["active"] is True


class TestConflictResolutionAPINoService:
    @pytest.fixture
    def client(self):
        from flask import Flask
        from copilot_core.api.v1.conflict_resolution import bp
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["COPILOT_SERVICES"] = {}
        app.register_blueprint(bp)
        with app.test_client() as c:
            yield c

    def test_state_503(self, client):
        resp = client.get("/api/v1/conflicts/state")
        assert resp.status_code == 503

    def test_evaluate_503(self, client):
        resp = client.post("/api/v1/conflicts/evaluate", json={})
        assert resp.status_code == 503

    def test_strategy_503(self, client):
        resp = client.post("/api/v1/conflicts/strategy", json={"strategy": "weighted"})
        assert resp.status_code == 503
