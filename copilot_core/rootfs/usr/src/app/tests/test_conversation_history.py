"""Tests for Conversation History API Blueprint."""

import importlib
import json
import os
import sqlite3
import tempfile
import time
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask

from copilot_core.conversation_memory import ConversationMemory


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Temporary SQLite database for conversation memory."""
    return str(tmp_path / "test_conv.db")


@pytest.fixture
def memory(tmp_db):
    """ConversationMemory with temp DB."""
    return ConversationMemory(db_path=tmp_db)


@pytest.fixture
def memory_with_data(memory):
    """ConversationMemory with some test data."""
    memory.store_message("user", "Mach das Licht an", conversation_id="conv1")
    memory.store_message("assistant", "Licht im Wohnzimmer eingeschaltet.", conversation_id="conv1")
    memory.store_message("user", "Wie ist das Wetter?", conversation_id="conv2")
    memory.store_message("assistant", "Heute sonnig, 22 Grad.", conversation_id="conv2")
    memory.store_message("user", "Stelle die Heizung auf 22 Grad", conversation_id="conv1")
    return memory


def _make_test_app(memory):
    """Create Flask app with conversation_history blueprint."""
    with patch("copilot_core.api.v1.conversation_history.require_token", lambda f: f):
        import copilot_core.api.v1.conversation_history as mod
        importlib.reload(mod)

    app = Flask(__name__)
    app.config["TESTING"] = True
    mod.init_conversation_history_api(memory)
    app.register_blueprint(mod.conversation_history_bp)
    return app


# ── History Endpoint ──────────────────────────────────────────────────────

class TestConversationHistory:
    """Tests for /api/v1/conversation/history."""

    def test_get_history(self, memory_with_data):
        app = _make_test_app(memory_with_data)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/history")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert data["total"] == 5
            assert len(data["messages"]) == 5

    def test_get_history_with_limit(self, memory_with_data):
        app = _make_test_app(memory_with_data)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/history?limit=2")
            data = resp.get_json()
            assert data["ok"] is True
            assert len(data["messages"]) == 2
            assert data["total"] == 5

    def test_get_history_with_offset(self, memory_with_data):
        app = _make_test_app(memory_with_data)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/history?limit=2&offset=3")
            data = resp.get_json()
            assert len(data["messages"]) == 2
            assert data["offset"] == 3

    def test_get_history_filter_role(self, memory_with_data):
        app = _make_test_app(memory_with_data)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/history?role=user")
            data = resp.get_json()
            assert all(m["role"] == "user" for m in data["messages"])
            assert data["total"] == 3

    def test_get_history_empty(self, memory):
        app = _make_test_app(memory)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/history")
            data = resp.get_json()
            assert data["ok"] is True
            assert data["total"] == 0
            assert data["messages"] == []

    def test_get_history_max_limit(self, memory_with_data):
        app = _make_test_app(memory_with_data)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/history?limit=9999")
            data = resp.get_json()
            assert data["limit"] == 200  # clamped to max

    def test_message_fields(self, memory_with_data):
        app = _make_test_app(memory_with_data)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/history?limit=1")
            data = resp.get_json()
            msg = data["messages"][0]
            assert "id" in msg
            assert "timestamp" in msg
            assert "role" in msg
            assert "content" in msg
            assert "character" in msg
            assert "topics" in msg
            assert isinstance(msg["topics"], list)


# ── Conversation by ID ────────────────────────────────────────────────────

class TestConversationById:
    """Tests for /api/v1/conversation/history/<conversation_id>."""

    def test_get_conversation(self, memory_with_data):
        app = _make_test_app(memory_with_data)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/history/conv1")
            data = resp.get_json()
            assert data["ok"] is True
            assert data["conversation_id"] == "conv1"
            assert len(data["messages"]) == 3

    def test_get_conversation_empty(self, memory_with_data):
        app = _make_test_app(memory_with_data)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/history/nonexistent")
            data = resp.get_json()
            assert data["ok"] is True
            assert data["messages"] == []


# ── Preferences ───────────────────────────────────────────────────────────

class TestPreferences:
    """Tests for /api/v1/conversation/preferences."""

    def test_get_preferences(self, memory_with_data):
        app = _make_test_app(memory_with_data)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/preferences")
            data = resp.get_json()
            assert data["ok"] is True
            assert isinstance(data["preferences"], list)

    def test_preference_fields(self, memory):
        memory.store_message("user", "Ich mag es bei 22 Grad und Temperatur warm")
        app = _make_test_app(memory)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/preferences")
            data = resp.get_json()
            if data["preferences"]:
                pref = data["preferences"][0]
                assert "key" in pref
                assert "value" in pref
                assert "confidence" in pref
                assert "source" in pref


# ── Stats ─────────────────────────────────────────────────────────────────

class TestStats:
    """Tests for /api/v1/conversation/stats."""

    def test_get_stats(self, memory_with_data):
        app = _make_test_app(memory_with_data)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/stats")
            data = resp.get_json()
            assert data["ok"] is True
            assert data["total_messages"] == 5
            assert data["user_messages"] == 3
            assert data["assistant_messages"] == 2

    def test_stats_empty(self, memory):
        app = _make_test_app(memory)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/stats")
            data = resp.get_json()
            assert data["ok"] is True
            assert data["total_messages"] == 0


# ── No Memory (503) ──────────────────────────────────────────────────────

class TestNoMemory:
    """Tests when ConversationMemory is not initialized."""

    def test_history_503(self):
        app = _make_test_app(None)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/history")
            assert resp.status_code == 503

    def test_preferences_503(self):
        app = _make_test_app(None)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/preferences")
            assert resp.status_code == 503

    def test_stats_503(self):
        app = _make_test_app(None)
        with app.test_client() as c:
            resp = c.get("/api/v1/conversation/stats")
            assert resp.status_code == 503
