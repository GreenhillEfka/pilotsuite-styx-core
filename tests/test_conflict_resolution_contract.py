from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import conflict_resolution as module  # noqa: E402
from copilot_core.storage.conflict_resolution import ConflictDetail, ConflictState  # noqa: E402


class FakeResolver:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.evaluate_calls: list[tuple[dict[str, dict[str, float]], dict[str, float]]] = []
        self.evaluate_from_store_calls: list[list[str] | None] = []
        self.strategy_calls: list[tuple[str, str | None]] = []
        self._state = ConflictState(
            active=False,
            conflicts=[],
            users_involved=["anna"],
            resolution="weighted",
            resolved_mood={"comfort": 0.5, "frugality": 0.5, "joy": 0.5},
        )

    @property
    def state(self):
        if self.raise_on == "state":
            raise RuntimeError("state exploded")
        return self._state

    def evaluate(self, user_moods, user_priorities):
        if self.raise_on == "evaluate":
            raise RuntimeError("evaluate exploded")
        self.evaluate_calls.append((user_moods, user_priorities))
        self._state = ConflictState(
            active=True,
            conflicts=[
                ConflictDetail("comfort", "anna", "bob", 0.9, 0.1, 0.8),
                ConflictDetail("frugality", "anna", "bob", 0.2, 0.8, 0.6),
            ],
            users_involved=["anna", "bob"],
            resolution="weighted",
            resolved_mood={"comfort": 0.6, "frugality": 0.4, "joy": 0.5},
        )
        return self._state

    def evaluate_from_store(self, active_user_ids=None):
        if self.raise_on == "evaluate_from_store":
            raise RuntimeError("store exploded")
        self.evaluate_from_store_calls.append(active_user_ids)
        self._state = ConflictState(
            active=False,
            conflicts=[],
            users_involved=active_user_ids or ["anna", "bob"],
            resolution="weighted",
            resolved_mood={"comfort": 0.55, "frugality": 0.45, "joy": 0.5},
        )
        return self._state

    def set_strategy(self, strategy, override_user=None):
        if self.raise_on == "set_strategy_runtime":
            raise RuntimeError("strategy exploded")
        if strategy == "invalid":
            raise ValueError("Unknown strategy: invalid. Valid: ('weighted', 'compromise', 'override')")
        self.strategy_calls.append((strategy, override_user))
        self._state.resolution = strategy
        self._state.override_user = override_user


class ExplodingState:
    def to_dict(self):
        raise RuntimeError("state exploded")


def _build_client(monkeypatch, *, authorized: bool = True, resolver=None):
    monkeypatch.setattr(module, "_validate_token", lambda _request: authorized)

    app = Flask(__name__)
    app.config["COPILOT_SERVICES"] = {"conflict_resolver": resolver} if resolver is not None else {}
    app.register_blueprint(module.bp)
    return app.test_client()


def test_conflict_resolution_contract_covers_all_routes(monkeypatch) -> None:
    resolver = FakeResolver()
    client = _build_client(monkeypatch, resolver=resolver)

    response = client.get("/api/v1/conflicts/state")
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "active": False,
        "conflict_count": 0,
        "users_involved": ["anna"],
        "resolution": "weighted",
        "override_user": None,
        "resolved_mood": {"comfort": 0.5, "frugality": 0.5, "joy": 0.5},
        "details": [],
    }

    response = client.post(
        "/api/v1/conflicts/evaluate",
        json={
            "user_moods": {
                "anna": {"comfort": 0.9, "frugality": 0.2, "joy": 0.5},
                "bob": {"comfort": 0.1, "frugality": 0.8, "joy": 0.5},
            },
            "user_priorities": {"anna": 0.75, "bob": 0.25},
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "active": True,
        "conflict_count": 2,
        "users_involved": ["anna", "bob"],
        "resolution": "weighted",
        "override_user": None,
        "resolved_mood": {"comfort": 0.6, "frugality": 0.4, "joy": 0.5},
        "details": [
            {
                "axis": "comfort",
                "user_a": "anna",
                "user_b": "bob",
                "value_a": 0.9,
                "value_b": 0.1,
                "divergence": 0.8,
            },
            {
                "axis": "frugality",
                "user_a": "anna",
                "user_b": "bob",
                "value_a": 0.2,
                "value_b": 0.8,
                "divergence": 0.6,
            },
        ],
    }
    assert resolver.evaluate_calls == [
        (
            {
                "anna": {"comfort": 0.9, "frugality": 0.2, "joy": 0.5},
                "bob": {"comfort": 0.1, "frugality": 0.8, "joy": 0.5},
            },
            {"anna": 0.75, "bob": 0.25},
        )
    ]

    response = client.post("/api/v1/conflicts/evaluate", json={"active_user_ids": [" anna ", "bob"]})
    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "active": False,
        "conflict_count": 0,
        "users_involved": ["anna", "bob"],
        "resolution": "weighted",
        "override_user": None,
        "resolved_mood": {"comfort": 0.55, "frugality": 0.45, "joy": 0.5},
        "details": [],
    }
    assert resolver.evaluate_from_store_calls == [["anna", "bob"]]

    response = client.post("/api/v1/conflicts/strategy", json={"strategy": "override", "override_user": " anna "})
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "strategy": "override", "override_user": "anna"}
    assert resolver.strategy_calls == [("override", "anna")]


def test_conflict_resolution_contract_hardens_uninitialized_validation_and_runtime_errors(monkeypatch) -> None:
    client = _build_client(monkeypatch, resolver=None)

    response = client.get("/api/v1/conflicts/state")
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "conflict_resolver not initialized"}

    response = client.post("/api/v1/conflicts/evaluate", json={})
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "conflict_resolver not initialized"}

    response = client.post("/api/v1/conflicts/strategy", json={"strategy": "weighted"})
    assert response.status_code == 503
    assert response.get_json() == {"ok": False, "error": "conflict_resolver not initialized"}

    resolver = FakeResolver()
    client = _build_client(monkeypatch, resolver=resolver)

    response = client.post("/api/v1/conflicts/evaluate", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON object required"}

    response = client.post("/api/v1/conflicts/evaluate", json={"user_moods": {}})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "user_moods and user_priorities must be provided together"}

    response = client.post("/api/v1/conflicts/evaluate", json={"user_moods": [], "user_priorities": {}})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "user_moods must be an object"}

    response = client.post("/api/v1/conflicts/evaluate", json={"user_moods": {"anna": []}, "user_priorities": {"anna": 1}})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "each user_moods entry must be an object"}

    response = client.post(
        "/api/v1/conflicts/evaluate",
        json={"user_moods": {"anna": {"comfort": "high"}}, "user_priorities": {"anna": 1}},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "mood values must be numeric"}

    response = client.post(
        "/api/v1/conflicts/evaluate",
        json={"user_moods": {"anna": {"comfort": 0.5}}, "user_priorities": {"anna": "high"}},
    )
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "user_priorities values must be numeric"}

    response = client.post("/api/v1/conflicts/evaluate", json={"active_user_ids": "anna"})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "active_user_ids must be a list of non-empty strings"}

    response = client.post("/api/v1/conflicts/evaluate", json={"active_user_ids": ["anna", "  "]})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "active_user_ids must be a list of non-empty strings"}

    response = client.post("/api/v1/conflicts/strategy", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON object required"}

    response = client.post("/api/v1/conflicts/strategy", json={})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "strategy required"}

    response = client.post("/api/v1/conflicts/strategy", json={"strategy": 7})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "strategy required"}

    response = client.post("/api/v1/conflicts/strategy", json={"strategy": "override", "override_user": 9})
    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "override_user must be a non-empty string"}

    response = client.post("/api/v1/conflicts/strategy", json={"strategy": "invalid"})
    assert response.status_code == 400
    assert response.get_json() == {
        "ok": False,
        "error": "Unknown strategy: invalid. Valid: ('weighted', 'compromise', 'override')",
    }

    resolver._state = ExplodingState()
    response = client.get("/api/v1/conflicts/state")
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "state exploded"}

    resolver.raise_on = "evaluate"
    response = client.post(
        "/api/v1/conflicts/evaluate",
        json={
            "user_moods": {
                "anna": {"comfort": 0.9, "frugality": 0.2, "joy": 0.5},
                "bob": {"comfort": 0.1, "frugality": 0.8, "joy": 0.5},
            },
            "user_priorities": {"anna": 0.75, "bob": 0.25},
        },
    )
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "evaluate exploded"}

    resolver.raise_on = "evaluate_from_store"
    response = client.post("/api/v1/conflicts/evaluate", json={})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "store exploded"}

    resolver.raise_on = "set_strategy_runtime"
    response = client.post("/api/v1/conflicts/strategy", json={"strategy": "weighted"})
    assert response.status_code == 500
    assert response.get_json() == {"ok": False, "error": "strategy exploded"}


def test_conflict_resolution_contract_requires_authentication(monkeypatch) -> None:
    client = _build_client(monkeypatch, authorized=False, resolver=FakeResolver())

    response = client.get("/api/v1/conflicts/state")
    assert response.status_code == 401
    assert response.get_json() == {"error": "unauthorized"}
