"""Comprehensive tests for Module Registry API and ModuleRegistry service.

Covers:
  - GET    /api/v1/modules              (list)
  - GET    /api/v1/modules/<id>         (single)
  - POST   /api/v1/modules              (create / upsert)
  - POST   /api/v1/modules/<id>/configure  (patch-like)
  - PUT    /api/v1/modules/<id>         (full replace)
  - DELETE /api/v1/modules/<id>         (remove)
  - Authentication enforcement
  - ModuleRegistry unit tests (predicates, autonomy helpers, singleton)
"""

import os
import sqlite3
import tempfile
import threading

import pytest

from copilot_core.app import create_app
from copilot_core.module_registry import (
    ModuleRegistry,
    VALID_STATES,
    DEFAULT_STATE,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_data(tmp_path):
    """Provide a temporary data directory and set MODULE_STATES_DB."""
    db_path = str(tmp_path / "module_states.db")
    os.environ["MODULE_STATES_DB"] = db_path
    yield tmp_path, db_path
    os.environ.pop("MODULE_STATES_DB", None)


@pytest.fixture()
def registry(tmp_data):
    """Fresh ModuleRegistry backed by a temp SQLite DB."""
    _, db_path = tmp_data
    reg = ModuleRegistry(db_path=db_path)
    yield reg


@pytest.fixture()
def app(tmp_data):
    """Flask test app with temp data directory."""
    tmp_path, db_path = tmp_data
    app = create_app()
    from dataclasses import replace

    cfg = app.config["COPILOT_CFG"]
    app.config["COPILOT_CFG"] = replace(
        cfg,
        data_dir=str(tmp_path),
        brain_graph_json_path=str(tmp_path / "brain_graph.db"),
        events_jsonl_path=str(tmp_path / "events.jsonl"),
        candidates_json_path=str(tmp_path / "candidates.json"),
        brain_graph_persist=True,
    )

    # Wire a fresh registry into the module_control blueprint
    from copilot_core.api.v1.module_control import init_module_control_api

    reg = ModuleRegistry(db_path=db_path)
    init_module_control_api(reg)

    yield app


@pytest.fixture()
def client(app):
    """Flask test client."""
    with app.test_client() as c:
        yield c


# ── Helper ──────────────────────────────────────────────────────────


def _json(response):
    """Shortcut for response JSON + status code."""
    return response.get_json(), response.status_code


# ====================================================================
# 1) GET /api/v1/modules  (list)
# ====================================================================


class TestModulesGetList:
    """GET /api/v1/modules — list all explicitly-configured modules."""

    def test_empty_list(self, client):
        j, status = _json(client.get("/api/v1/modules"))
        assert status == 200
        assert j["ok"] is True
        assert j["modules"] == {}

    def test_list_after_create(self, client):
        client.post("/api/v1/modules", json={"module_id": "mood_engine", "state": "learning"})
        client.post("/api/v1/modules", json={"module_id": "habitus_miner", "state": "off"})

        j, status = _json(client.get("/api/v1/modules"))
        assert status == 200
        assert j["ok"] is True
        assert j["modules"]["mood_engine"] == "learning"
        assert j["modules"]["habitus_miner"] == "off"
        assert len(j["modules"]) == 2

    def test_list_excludes_deleted(self, client):
        client.post("/api/v1/modules", json={"module_id": "temp_mod", "state": "active"})
        client.delete("/api/v1/modules/temp_mod")

        j, _ = _json(client.get("/api/v1/modules"))
        assert "temp_mod" not in j["modules"]


# ====================================================================
# 2) GET /api/v1/modules/<id>  (single)
# ====================================================================


class TestModulesGetSingle:
    """GET /api/v1/modules/<id> — get single module state."""

    def test_unconfigured_returns_default(self, client):
        """Modules never set should return the default state 'active'."""
        j, status = _json(client.get("/api/v1/modules/never_configured"))
        assert status == 200
        assert j["ok"] is True
        assert j["module_id"] == "never_configured"
        assert j["state"] == DEFAULT_STATE

    def test_configured_returns_state(self, client):
        client.post("/api/v1/modules", json={"module_id": "brain_graph", "state": "learning"})
        j, status = _json(client.get("/api/v1/modules/brain_graph"))
        assert status == 200
        assert j["state"] == "learning"

    def test_returns_updated_state(self, client):
        client.post("/api/v1/modules", json={"module_id": "m1", "state": "active"})
        client.post("/api/v1/modules", json={"module_id": "m1", "state": "off"})
        j, _ = _json(client.get("/api/v1/modules/m1"))
        assert j["state"] == "off"


# ====================================================================
# 3) POST /api/v1/modules  (create / upsert)
# ====================================================================


class TestModulesPost:
    """POST /api/v1/modules — create or update a module state."""

    # ── Success paths ───────────────────────────────────────────────

    def test_create_new_module(self, client):
        j, status = _json(
            client.post("/api/v1/modules", json={"module_id": "new_mod", "state": "learning"})
        )
        assert status == 200
        assert j["ok"] is True
        assert j["module_id"] == "new_mod"
        assert j["state"] == "learning"
        assert j["action"] == "created"

    def test_update_existing_module(self, client):
        client.post("/api/v1/modules", json={"module_id": "ex", "state": "active"})
        j, status = _json(
            client.post("/api/v1/modules", json={"module_id": "ex", "state": "off"})
        )
        assert status == 200
        assert j["action"] == "updated"
        assert j["state"] == "off"

    @pytest.mark.parametrize("state", sorted(VALID_STATES))
    def test_all_valid_states(self, client, state):
        j, status = _json(
            client.post("/api/v1/modules", json={"module_id": f"mod_{state}", "state": state})
        )
        assert status == 200
        assert j["state"] == state

    def test_state_case_insensitive(self, client):
        """State should be normalized to lowercase."""
        j, status = _json(
            client.post("/api/v1/modules", json={"module_id": "ci", "state": "LEARNING"})
        )
        assert status == 200
        assert j["state"] == "learning"

    def test_state_whitespace_stripped(self, client):
        j, status = _json(
            client.post("/api/v1/modules", json={"module_id": "ws", "state": "  off  "})
        )
        assert status == 200
        assert j["state"] == "off"

    # ── Error paths ────────────────────────────────────────────────

    def test_missing_module_id(self, client):
        j, status = _json(client.post("/api/v1/modules", json={"state": "active"}))
        assert status == 400
        assert j["ok"] is False
        assert "module_id" in j["error"].lower()

    def test_missing_state(self, client):
        j, status = _json(client.post("/api/v1/modules", json={"module_id": "x"}))
        assert status == 400
        assert j["ok"] is False

    def test_empty_module_id(self, client):
        j, status = _json(
            client.post("/api/v1/modules", json={"module_id": "", "state": "active"})
        )
        assert status == 400

    def test_empty_state(self, client):
        j, status = _json(
            client.post("/api/v1/modules", json={"module_id": "x", "state": ""})
        )
        assert status == 400

    def test_invalid_state(self, client):
        j, status = _json(
            client.post("/api/v1/modules", json={"module_id": "x", "state": "invalid"})
        )
        assert status == 422
        assert j["ok"] is False
        assert "valid_states" in j

    def test_empty_body(self, client):
        j, status = _json(
            client.post("/api/v1/modules", data="", content_type="application/json")
        )
        assert status == 400

    def test_no_json_content_type(self, client):
        """Non-JSON body should be handled gracefully (silent=True)."""
        j, status = _json(
            client.post("/api/v1/modules", data="not json", content_type="text/plain")
        )
        assert status == 400


# ====================================================================
# 4) POST /api/v1/modules/<id>/configure  (PATCH-like)
# ====================================================================


class TestModulesConfigure:
    """POST /api/v1/modules/<id>/configure — set state."""

    def test_configure_new_module(self, client):
        j, status = _json(
            client.post("/api/v1/modules/cfg_new/configure", json={"state": "learning"})
        )
        assert status == 200
        assert j["ok"] is True
        assert j["module_id"] == "cfg_new"
        assert j["state"] == "learning"
        assert "previous" in j

    def test_configure_updates_previous(self, client):
        client.post("/api/v1/modules/cfg_prev/configure", json={"state": "active"})
        j, _ = _json(
            client.post("/api/v1/modules/cfg_prev/configure", json={"state": "off"})
        )
        assert j["previous"] == "active"
        assert j["state"] == "off"

    def test_configure_missing_state(self, client):
        j, status = _json(
            client.post("/api/v1/modules/cfg_bad/configure", json={})
        )
        assert status == 400
        assert j["ok"] is False

    def test_configure_invalid_state(self, client):
        j, status = _json(
            client.post("/api/v1/modules/cfg_bad/configure", json={"state": "broken"})
        )
        assert status == 422
        assert j["ok"] is False
        assert "valid_states" in j

    def test_configure_case_insensitive(self, client):
        j, status = _json(
            client.post("/api/v1/modules/cfg_ci/configure", json={"state": "OFF"})
        )
        assert status == 200
        assert j["state"] == "off"


# ====================================================================
# 5) PUT /api/v1/modules/<id>  (full replace)
# ====================================================================


class TestModulesPut:
    """PUT /api/v1/modules/<id> — replace module state."""

    def test_put_creates_if_missing(self, client):
        j, status = _json(
            client.put("/api/v1/modules/put_new", json={"state": "learning"})
        )
        assert status == 200
        assert j["ok"] is True
        assert j["action"] == "created"
        assert j["state"] == "learning"

    def test_put_updates_existing(self, client):
        client.post("/api/v1/modules", json={"module_id": "put_ex", "state": "active"})
        j, status = _json(
            client.put("/api/v1/modules/put_ex", json={"state": "off"})
        )
        assert status == 200
        assert j["action"] == "updated"
        assert j["previous"] == "active"
        assert j["state"] == "off"

    def test_put_missing_state(self, client):
        j, status = _json(client.put("/api/v1/modules/put_bad", json={}))
        assert status == 400

    def test_put_invalid_state(self, client):
        j, status = _json(
            client.put("/api/v1/modules/put_bad", json={"state": "nope"})
        )
        assert status == 422

    def test_put_all_valid_states(self, client):
        for state in sorted(VALID_STATES):
            j, status = _json(
                client.put(f"/api/v1/modules/put_{state}", json={"state": state})
            )
            assert status == 200
            assert j["state"] == state


# ====================================================================
# 6) DELETE /api/v1/modules/<id>
# ====================================================================


class TestModulesDelete:
    """DELETE /api/v1/modules/<id> — remove explicit state."""

    def test_delete_existing(self, client):
        client.post("/api/v1/modules", json={"module_id": "del_me", "state": "off"})
        j, status = _json(client.delete("/api/v1/modules/del_me"))
        assert status == 200
        assert j["ok"] is True
        assert j["module_id"] == "del_me"
        assert j["deleted_state"] == "off"

    def test_delete_reverts_to_default(self, client):
        """After deletion, GET should return default state."""
        client.post("/api/v1/modules", json={"module_id": "del_rev", "state": "off"})
        client.delete("/api/v1/modules/del_rev")
        j, _ = _json(client.get("/api/v1/modules/del_rev"))
        assert j["state"] == DEFAULT_STATE

    def test_delete_nonexistent_returns_404(self, client):
        j, status = _json(client.delete("/api/v1/modules/nonexistent_xyz"))
        assert status == 404
        assert j["ok"] is False

    def test_delete_removed_from_list(self, client):
        client.post("/api/v1/modules", json={"module_id": "del_list", "state": "learning"})
        client.delete("/api/v1/modules/del_list")
        j, _ = _json(client.get("/api/v1/modules"))
        assert "del_list" not in j["modules"]

    def test_double_delete_returns_404(self, client):
        """Deleting twice should fail the second time."""
        client.post("/api/v1/modules", json={"module_id": "dbl_del", "state": "off"})
        client.delete("/api/v1/modules/dbl_del")
        j, status = _json(client.delete("/api/v1/modules/dbl_del"))
        assert status == 404


# ====================================================================
# 7) Authentication enforcement
# ====================================================================


class TestModulesAuth:
    """Verify all module endpoints require auth when configured."""

    @pytest.fixture(autouse=True)
    def _set_auth(self, tmp_data, monkeypatch):
        """Enable auth with a known token."""
        monkeypatch.setenv("COPILOT_AUTH_TOKEN", "secret-test-token")
        monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "true")
        # Reset token cache so new env vars take effect
        import copilot_core.api.security as sec
        sec._token_cache = ("", 0.0)

    def _headers(self):
        return {"Authorization": "Bearer secret-test-token"}

    def test_get_list_requires_auth(self, client):
        _, status = _json(client.get("/api/v1/modules"))
        assert status == 401

    def test_get_list_with_auth(self, client):
        _, status = _json(client.get("/api/v1/modules", headers=self._headers()))
        assert status == 200

    def test_get_single_requires_auth(self, client):
        _, status = _json(client.get("/api/v1/modules/m"))
        assert status == 401

    def test_post_requires_auth(self, client):
        _, status = _json(
            client.post("/api/v1/modules", json={"module_id": "a", "state": "active"})
        )
        assert status == 401

    def test_put_requires_auth(self, client):
        _, status = _json(
            client.put("/api/v1/modules/m", json={"state": "active"})
        )
        assert status == 401

    def test_delete_requires_auth(self, client):
        _, status = _json(client.delete("/api/v1/modules/m"))
        assert status == 401

    def test_configure_requires_auth(self, client):
        _, status = _json(
            client.post("/api/v1/modules/m/configure", json={"state": "active"})
        )
        assert status == 401

    def test_x_auth_token_header(self, client):
        """X-Auth-Token header should also work."""
        _, status = _json(
            client.get("/api/v1/modules", headers={"X-Auth-Token": "secret-test-token"})
        )
        assert status == 200

    def test_wrong_token_rejected(self, client):
        _, status = _json(
            client.get("/api/v1/modules", headers={"Authorization": "Bearer wrong"})
        )
        assert status == 401


# ====================================================================
# 8) State transitions (full matrix)
# ====================================================================


class TestStateTransitions:
    """Verify all valid state transitions work."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            ("active", "learning"),
            ("active", "off"),
            ("learning", "active"),
            ("learning", "off"),
            ("off", "active"),
            ("off", "learning"),
            ("active", "active"),   # idempotent
            ("learning", "learning"),
            ("off", "off"),
        ],
    )
    def test_transition(self, client, from_state, to_state):
        mid = f"trans_{from_state}_{to_state}"
        client.post("/api/v1/modules", json={"module_id": mid, "state": from_state})
        j, status = _json(
            client.put(f"/api/v1/modules/{mid}", json={"state": to_state})
        )
        assert status == 200
        assert j["state"] == to_state


# ====================================================================
# 9) ModuleRegistry unit tests
# ====================================================================


class TestModuleRegistryUnit:
    """Unit tests for the ModuleRegistry class."""

    def test_get_state_default(self, registry):
        assert registry.get_state("unknown") == DEFAULT_STATE

    def test_set_and_get(self, registry):
        assert registry.set_state("m1", "learning") is True
        assert registry.get_state("m1") == "learning"

    def test_set_invalid_state(self, registry):
        assert registry.set_state("m1", "bogus") is False

    def test_get_all_states_empty(self, registry):
        assert registry.get_all_states() == {}

    def test_get_all_states(self, registry):
        registry.set_state("a", "active")
        registry.set_state("b", "off")
        states = registry.get_all_states()
        assert states == {"a": "active", "b": "off"}

    def test_upsert_overwrites(self, registry):
        registry.set_state("m", "active")
        registry.set_state("m", "off")
        assert registry.get_state("m") == "off"

    # ── Predicates ──────────────────────────────────────────────────

    def test_is_active_default(self, registry):
        assert registry.is_active("unconfigured") is True

    def test_is_active_explicit(self, registry):
        registry.set_state("m", "active")
        assert registry.is_active("m") is True

    def test_is_learning(self, registry):
        registry.set_state("m", "learning")
        assert registry.is_learning("m") is True
        assert registry.is_active("m") is False

    def test_is_off(self, registry):
        registry.set_state("m", "off")
        assert registry.is_off("m") is True
        assert registry.is_active("m") is False

    # ── Autonomy helpers ────────────────────────────────────────────

    def test_should_auto_apply_both_active(self, registry):
        registry.set_state("src", "active")
        registry.set_state("tgt", "active")
        assert registry.should_auto_apply("src", "tgt") is True

    def test_should_auto_apply_one_learning(self, registry):
        registry.set_state("src", "active")
        registry.set_state("tgt", "learning")
        assert registry.should_auto_apply("src", "tgt") is False

    def test_should_auto_apply_one_off(self, registry):
        registry.set_state("src", "active")
        registry.set_state("tgt", "off")
        assert registry.should_auto_apply("src", "tgt") is False

    def test_should_suggest_active(self, registry):
        registry.set_state("m", "active")
        assert registry.should_suggest("m") is True

    def test_should_suggest_learning(self, registry):
        registry.set_state("m", "learning")
        assert registry.should_suggest("m") is True

    def test_should_suggest_off(self, registry):
        registry.set_state("m", "off")
        assert registry.should_suggest("m") is False

    def test_should_collect_data_active(self, registry):
        assert registry.should_collect_data("unconfigured") is True

    def test_should_collect_data_learning(self, registry):
        registry.set_state("m", "learning")
        assert registry.should_collect_data("m") is True

    def test_should_collect_data_off(self, registry):
        registry.set_state("m", "off")
        assert registry.should_collect_data("m") is False

    # ── Suggestion mode ─────────────────────────────────────────────

    def test_suggestion_mode_auto_apply(self, registry):
        registry.set_state("s", "active")
        registry.set_state("t", "active")
        assert registry.get_suggestion_mode("s", "t") == "auto_apply"

    def test_suggestion_mode_manual(self, registry):
        registry.set_state("s", "active")
        registry.set_state("t", "learning")
        assert registry.get_suggestion_mode("s", "t") == "manual"

    def test_suggestion_mode_suppress_src_off(self, registry):
        registry.set_state("s", "off")
        registry.set_state("t", "active")
        assert registry.get_suggestion_mode("s", "t") == "suppress"

    def test_suggestion_mode_suppress_tgt_off(self, registry):
        registry.set_state("s", "learning")
        registry.set_state("t", "off")
        assert registry.get_suggestion_mode("s", "t") == "suppress"

    def test_suggestion_mode_both_learning(self, registry):
        registry.set_state("s", "learning")
        registry.set_state("t", "learning")
        assert registry.get_suggestion_mode("s", "t") == "manual"

    # ── Singleton ───────────────────────────────────────────────────

    def test_singleton_returns_same_instance(self, tmp_data):
        _, db_path = tmp_data
        ModuleRegistry._reset_instance()
        a = ModuleRegistry.get_instance(db_path=db_path)
        b = ModuleRegistry.get_instance()
        assert a is b
        ModuleRegistry._reset_instance()

    def test_reset_instance(self, tmp_data):
        _, db_path = tmp_data
        ModuleRegistry._reset_instance()
        a = ModuleRegistry.get_instance(db_path=db_path)
        ModuleRegistry._reset_instance()
        b = ModuleRegistry.get_instance(db_path=db_path)
        assert a is not b
        ModuleRegistry._reset_instance()


# ====================================================================
# 10) Edge cases & integration
# ====================================================================


class TestModulesEdgeCases:
    """Edge cases and integration scenarios."""

    def test_create_then_list_then_delete_lifecycle(self, client):
        """Full CRUD lifecycle."""
        # Create
        j, _ = _json(
            client.post("/api/v1/modules", json={"module_id": "lifecycle", "state": "learning"})
        )
        assert j["action"] == "created"

        # Read
        j, _ = _json(client.get("/api/v1/modules/lifecycle"))
        assert j["state"] == "learning"

        # Update via PUT
        j, _ = _json(
            client.put("/api/v1/modules/lifecycle", json={"state": "active"})
        )
        assert j["state"] == "active"

        # Update via configure
        j, _ = _json(
            client.post("/api/v1/modules/lifecycle/configure", json={"state": "off"})
        )
        assert j["state"] == "off"

        # List should contain it
        j, _ = _json(client.get("/api/v1/modules"))
        assert "lifecycle" in j["modules"]

        # Delete
        j, _ = _json(client.delete("/api/v1/modules/lifecycle"))
        assert j["ok"] is True

        # After delete, reverts to default
        j, _ = _json(client.get("/api/v1/modules/lifecycle"))
        assert j["state"] == DEFAULT_STATE

    def test_many_modules(self, client):
        """Create many modules and verify listing."""
        for i in range(20):
            state = sorted(VALID_STATES)[i % 3]
            client.post("/api/v1/modules", json={"module_id": f"bulk_{i}", "state": state})

        j, _ = _json(client.get("/api/v1/modules"))
        assert len(j["modules"]) == 20

    def test_special_characters_in_module_id(self, client):
        """Module IDs with dots, dashes, underscores."""
        mid = "my-module.v2_beta"
        j, status = _json(
            client.post("/api/v1/modules", json={"module_id": mid, "state": "active"})
        )
        assert status == 200
        j, _ = _json(client.get(f"/api/v1/modules/{mid}"))
        assert j["module_id"] == mid

    def test_post_upsert_preserves_other_modules(self, client):
        """Updating one module should not affect others."""
        client.post("/api/v1/modules", json={"module_id": "a", "state": "active"})
        client.post("/api/v1/modules", json={"module_id": "b", "state": "learning"})
        client.post("/api/v1/modules", json={"module_id": "a", "state": "off"})

        j, _ = _json(client.get("/api/v1/modules"))
        assert j["modules"]["a"] == "off"
        assert j["modules"]["b"] == "learning"


# ====================================================================
# 11) Internal error handling paths (coverage)
# ====================================================================


class TestModuleRegistryErrorHandling:
    """Cover sqlite error handling branches in ModuleRegistry."""

    def test_set_state_sqlite_error_returns_false(self, registry, monkeypatch):
        class BoomConn:
            def execute(self, *args, **kwargs):
                raise sqlite3.Error("boom")

            def commit(self):
                return None

            def close(self):
                return None

        monkeypatch.setattr(registry, "_get_connection", lambda: BoomConn())
        assert registry.set_state("m1", "active") is False


class TestModuleControlInternalErrorPaths:
    """Force internal error branches in the Flask endpoints."""

    def test_get_registry_falls_back_to_singleton(self, tmp_data, monkeypatch):
        """When init_module_control_api() was not called, _get_registry() should
        return the ModuleRegistry singleton (coverage for that branch).
        """
        _, db_path = tmp_data

        import copilot_core.api.v1.module_control as mc
        import copilot_core.module_registry as mr

        # Ensure _get_registry() takes the singleton path
        monkeypatch.setattr(mc, "_registry", None)
        ModuleRegistry._reset_instance()
        monkeypatch.setattr(mr, "DB_PATH", db_path)

        reg = mc._get_registry()
        assert isinstance(reg, ModuleRegistry)
        assert getattr(reg, "_db_path") == db_path

        ModuleRegistry._reset_instance()

    def test_configure_returns_500_when_persist_fails(self, client, monkeypatch):
        import copilot_core.api.v1.module_control as mc

        class StubRegistry:
            def get_state(self, module_id):
                return DEFAULT_STATE

            def set_state(self, module_id, state):
                return False

        monkeypatch.setattr(mc, "_registry", StubRegistry())

        j, status = _json(
            client.post("/api/v1/modules/m/configure", json={"state": "active"})
        )
        assert status == 500
        assert j["ok"] is False

    def test_create_returns_500_when_persist_fails(self, client, monkeypatch):
        import copilot_core.api.v1.module_control as mc

        class StubRegistry:
            def get_state(self, module_id):
                return DEFAULT_STATE

            def get_all_states(self):
                return {}

            def set_state(self, module_id, state):
                return False

        monkeypatch.setattr(mc, "_registry", StubRegistry())

        j, status = _json(
            client.post("/api/v1/modules", json={"module_id": "m", "state": "active"})
        )
        assert status == 500
        assert j["ok"] is False

    def test_update_returns_500_when_persist_fails(self, client, monkeypatch):
        import copilot_core.api.v1.module_control as mc

        class StubRegistry:
            def get_state(self, module_id):
                return DEFAULT_STATE

            def get_all_states(self):
                return {"m": "active"}

            def set_state(self, module_id, state):
                return False

        monkeypatch.setattr(mc, "_registry", StubRegistry())

        j, status = _json(client.put("/api/v1/modules/m", json={"state": "off"}))
        assert status == 500
        assert j["ok"] is False

    def test_delete_returns_500_when_rowcount_zero(self, client, monkeypatch):
        import copilot_core.api.v1.module_control as mc

        class Cursor:
            rowcount = 0

        class Conn:
            def execute(self, *args, **kwargs):
                return Cursor()

            def commit(self):
                return None

            def close(self):
                return None

        class StubRegistry:
            _lock = threading.Lock()

            def get_state(self, module_id):
                return "off"

            def get_all_states(self):
                # Must exist to pass the 404 guard
                return {"m": "off"}

            def _get_connection(self):
                return Conn()

        monkeypatch.setattr(mc, "_registry", StubRegistry())

        j, status = _json(client.delete("/api/v1/modules/m"))
        assert status == 500
        assert j["ok"] is False

    def test_fallback_to_singleton_when_registry_not_initialized(self, tmp_data, monkeypatch):
        """Test that _get_registry falls back to ModuleRegistry.get_instance() when _registry is None."""
        import copilot_core.api.v1.module_control as mc
        from copilot_core.module_registry import ModuleRegistry, DB_PATH

        _, db_path = tmp_data
        ModuleRegistry._reset_instance()

        # Set the DB path for the singleton via module_registry module
        import copilot_core.module_registry as mr_module
        monkeypatch.setattr(mr_module, "DB_PATH", db_path)

        # Set _registry to None to trigger the fallback
        monkeypatch.setattr(mc, "_registry", None)

        # Call _get_registry - should fall back to singleton
        reg = mc._get_registry()
        assert isinstance(reg, ModuleRegistry)
        assert getattr(reg, "_db_path") == db_path

        ModuleRegistry._reset_instance()
