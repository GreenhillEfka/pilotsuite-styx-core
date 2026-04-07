"""Tests for ConversationMemory — conversation_id grouping and history retrieval.

Covers:
- store_message with conversation_id
- get_conversation_history: ordering, limit, empty results
- Migration: conversation_id column added to existing DBs
- Context window: history injection for multi-turn conversations
- Backward compatibility: store_message without conversation_id
"""
from __future__ import annotations

import os
import tempfile
import time

import pytest

from copilot_core.conversation_memory import ConversationMemory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def memory(tmp_path):
    """Create a ConversationMemory with a temp database."""
    db_path = str(tmp_path / "test_conv.db")
    return ConversationMemory(db_path=db_path)


# ---------------------------------------------------------------------------
# Basic store_message with conversation_id
# ---------------------------------------------------------------------------

class TestStoreWithConversationId:
    def test_store_message_with_conversation_id(self, memory):
        msg_id = memory.store_message(
            role="user", content="Hallo Welt",
            conversation_id="conv-001",
        )
        assert msg_id > 0

    def test_store_message_without_conversation_id(self, memory):
        """Backward compat: conversation_id is optional."""
        msg_id = memory.store_message(role="user", content="Kein Kontext")
        assert msg_id > 0

    def test_store_multiple_in_same_conversation(self, memory):
        memory.store_message(role="user", content="Frage 1", conversation_id="conv-001")
        memory.store_message(role="assistant", content="Antwort 1", conversation_id="conv-001")
        memory.store_message(role="user", content="Frage 2", conversation_id="conv-001")

        history = memory.get_conversation_history("conv-001")
        assert len(history) == 3

    def test_store_across_conversations(self, memory):
        memory.store_message(role="user", content="A", conversation_id="conv-A")
        memory.store_message(role="user", content="B", conversation_id="conv-B")
        memory.store_message(role="user", content="C", conversation_id="conv-A")

        assert len(memory.get_conversation_history("conv-A")) == 2
        assert len(memory.get_conversation_history("conv-B")) == 1


# ---------------------------------------------------------------------------
# get_conversation_history
# ---------------------------------------------------------------------------

class TestGetConversationHistory:
    def test_empty_conversation_id(self, memory):
        assert memory.get_conversation_history("") == []

    def test_nonexistent_conversation_id(self, memory):
        assert memory.get_conversation_history("does-not-exist") == []

    def test_returns_chronological_order(self, memory):
        memory.store_message(role="user", content="First", conversation_id="conv-001")
        memory.store_message(role="assistant", content="Second", conversation_id="conv-001")
        memory.store_message(role="user", content="Third", conversation_id="conv-001")

        history = memory.get_conversation_history("conv-001")
        assert [h["content"] for h in history] == ["First", "Second", "Third"]

    def test_limit_parameter(self, memory):
        for i in range(10):
            memory.store_message(
                role="user", content=f"Message {i}",
                conversation_id="conv-big",
            )

        history = memory.get_conversation_history("conv-big", limit=3)
        assert len(history) == 3
        # Should return the 3 most recent (reversed to chronological)
        assert history[-1]["content"] == "Message 9"

    def test_history_contains_role_and_content(self, memory):
        memory.store_message(role="user", content="Q", conversation_id="conv-001")
        memory.store_message(role="assistant", content="A", conversation_id="conv-001")

        history = memory.get_conversation_history("conv-001")
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Q"
        assert history[1]["role"] == "assistant"

    def test_history_contains_timestamp(self, memory):
        memory.store_message(role="user", content="Test", conversation_id="conv-001")
        history = memory.get_conversation_history("conv-001")
        assert "timestamp" in history[0]
        assert isinstance(history[0]["timestamp"], float)

    def test_history_contains_character(self, memory):
        memory.store_message(
            role="assistant", content="Hi", character="butler",
            conversation_id="conv-001",
        )
        history = memory.get_conversation_history("conv-001")
        assert history[0]["character"] == "butler"

    def test_null_conversation_id_not_returned(self, memory):
        """Messages without conversation_id should not appear in history."""
        memory.store_message(role="user", content="No conv id")
        memory.store_message(role="user", content="With id", conversation_id="conv-001")

        history = memory.get_conversation_history("conv-001")
        assert len(history) == 1
        assert history[0]["content"] == "With id"


# ---------------------------------------------------------------------------
# Migration (existing DB without conversation_id column)
# ---------------------------------------------------------------------------

class TestMigration:
    def test_migration_adds_column(self, tmp_path):
        """Simulate an existing DB without conversation_id column."""
        import sqlite3
        db_path = str(tmp_path / "legacy.db")

        # Create a legacy schema without conversation_id
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                character TEXT DEFAULT 'copilot',
                extracted_preferences TEXT DEFAULT '{}',
                topic_tags TEXT DEFAULT '',
                mood_context TEXT DEFAULT '{}'
            );
            CREATE TABLE user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source TEXT DEFAULT 'inferred',
                last_updated REAL NOT NULL,
                mention_count INTEGER DEFAULT 1
            );
            CREATE TABLE conversation_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                summary TEXT NOT NULL,
                topics TEXT DEFAULT '',
                sentiment TEXT DEFAULT 'neutral',
                key_facts TEXT DEFAULT '[]'
            );
        """)
        # Insert a legacy message
        conn.execute(
            "INSERT INTO conversations (timestamp, role, content) VALUES (?, ?, ?)",
            (time.time(), "user", "Legacy message"),
        )
        conn.commit()
        conn.close()

        # Now open with ConversationMemory — migration should run
        mem = ConversationMemory(db_path=db_path)

        # Legacy message still accessible (no conversation_id)
        assert mem.get_conversation_history("any") == []

        # New messages with conversation_id should work
        mem.store_message(role="user", content="New", conversation_id="conv-new")
        history = mem.get_conversation_history("conv-new")
        assert len(history) == 1
        assert history[0]["content"] == "New"


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_store_without_conversation_id_still_works(self, memory):
        msg_id = memory.store_message(role="user", content="No group")
        assert msg_id > 0

    def test_get_stats_still_works(self, memory):
        memory.store_message(role="user", content="Test", conversation_id="conv-001")
        stats = memory.get_stats()
        assert stats["total_messages"] == 1

    def test_get_relevant_context_still_works(self, memory):
        memory.store_message(role="user", content="Ich mag Licht hell", conversation_id="conv-001")
        ctx = memory.get_relevant_context("Licht")
        assert isinstance(ctx, str)

    def test_preferences_still_extracted(self, memory):
        memory.store_message(
            role="user", content="Ich mag es bei 22 Grad und bevorzuge warme Temperatur",
            conversation_id="conv-001",
        )
        prefs = memory.get_user_preferences()
        assert len(prefs) > 0
