"""Chat/RAG Analytics Contract Tests — Slice 62."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

from copilot_core.analytics.chat_analytics import (
    ChatAnalyticsStore,
    ChatEffectivenessMetricsV1,
    ChatEventV1,
    ChatEventType,
    ChatHistoryV1,
    ChatPatternEntryV1,
    ChatPatternsV1,
    ChatSource,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "chat_analytics.db"


@pytest.fixture
def store(temp_db: Path) -> ChatAnalyticsStore:
    """Create analytics store with temp database."""
    return ChatAnalyticsStore(temp_db)


class TestChatEventV1:
    """Test ChatEventV1 dataclass."""

    def test_event_creation(self) -> None:
        """Test basic event creation."""
        event = ChatEventV1(
            event_id="evt-001",
            session_id="session-001",
            zone_id="zone-living",
            event_type=ChatEventType.MESSAGE_RECEIVED,
            source=ChatSource.TELEGRAM,
            timestamp=time.time(),
            revision=1,
        )

        assert event.event_id == "evt-001"
        assert event.session_id == "session-001"
        assert event.zone_id == "zone-living"
        assert event.event_type == ChatEventType.MESSAGE_RECEIVED
        assert event.source == ChatSource.TELEGRAM

    def test_event_to_dict(self) -> None:
        """Test event serialization."""
        event = ChatEventV1(
            event_id="evt-002",
            session_id="session-002",
            zone_id="zone-bedroom",
            event_type=ChatEventType.RESPONSE_GENERATED,
            source=ChatSource.WEB,
            timestamp=1234567890.0,
            revision=1,
            metadata={"test": "value"},
        )

        d = event.to_dict()
        assert d["event_id"] == "evt-002"
        assert d["session_id"] == "session-002"
        assert d["zone_id"] == "zone-bedroom"
        assert d["event_type"] == "response_generated"
        assert d["source"] == "web"
        assert d["metadata"] == {"test": "value"}


class TestChatAnalyticsStore:
    """Test ChatAnalyticsStore operations."""

    def test_add_chat_event(self, store: ChatAnalyticsStore) -> None:
        """Test adding a chat event."""
        entry = store.add_chat_event(
            event_id="evt-001",
            session_id="session-001",
            zone_id="zone-living",
            event_type=ChatEventType.MESSAGE_RECEIVED,
            source=ChatSource.TELEGRAM,
        )

        assert entry.event_id == "evt-001"
        assert entry.session_id == "session-001"
        assert entry.revision == 1

    def test_revision_increments(self, store: ChatAnalyticsStore) -> None:
        """Test revision increments with each event."""
        store.add_chat_event(
            event_id=str(uuid.uuid4()),
            session_id="session-001",
            zone_id="zone-1",
            event_type=ChatEventType.MESSAGE_RECEIVED,
            source=ChatSource.TELEGRAM,
        )

        entry2 = store.add_chat_event(
            event_id=str(uuid.uuid4()),
            session_id="session-002",
            zone_id="zone-2",
            event_type=ChatEventType.RESPONSE_GENERATED,
            source=ChatSource.WEB,
        )

        assert entry2.revision == 2

    def test_build_chat_history(self, store: ChatAnalyticsStore) -> None:
        """Test building chat history."""
        for i in range(5):
            store.add_chat_event(
                event_id=f"evt-{i:03d}",
                session_id=f"session-{i:03d}",
                zone_id="zone-living",
                event_type=ChatEventType.MESSAGE_RECEIVED,
                source=ChatSource.TELEGRAM,
            )

        history = store.build_chat_history(limit=10)

        assert isinstance(history, ChatHistoryV1)
        assert history.total_count == 5
        assert len(history.events) == 5
        assert history.revision == 5

    def test_build_chat_history_filtered_by_session(self, store: ChatAnalyticsStore) -> None:
        """Test filtering history by session."""
        store.add_chat_event(
            event_id="evt-001",
            session_id="session-001",
            zone_id="zone-living",
            event_type=ChatEventType.MESSAGE_RECEIVED,
            source=ChatSource.TELEGRAM,
        )
        store.add_chat_event(
            event_id="evt-002",
            session_id="session-001",
            zone_id="zone-living",
            event_type=ChatEventType.RESPONSE_GENERATED,
            source=ChatSource.TELEGRAM,
        )
        store.add_chat_event(
            event_id="evt-003",
            session_id="session-002",
            zone_id="zone-bedroom",
            event_type=ChatEventType.MESSAGE_RECEIVED,
            source=ChatSource.WEB,
        )

        history = store.build_chat_history(session_id="session-001")

        assert history.total_count == 2
        assert all(e.session_id == "session-001" for e in history.events)

    def test_build_chat_history_with_revision_filter(self, store: ChatAnalyticsStore) -> None:
        """Test filtering history by revision."""
        for i in range(5):
            store.add_chat_event(
                event_id=f"evt-{i:03d}",
                session_id=f"session-{i:03d}",
                zone_id="zone-living",
                event_type=ChatEventType.MESSAGE_RECEIVED,
                source=ChatSource.TELEGRAM,
            )

        history = store.build_chat_history(since_revision=3)

        assert history.total_count == 2
        assert all(e.revision > 3 for e in history.events)

    def test_build_chat_patterns(self, store: ChatAnalyticsStore) -> None:
        """Test building chat patterns."""
        for i in range(10):
            store.add_chat_event(
                event_id=f"evt-living-{i:03d}",
                session_id=f"session-living-{i:03d}",
                zone_id="zone-living",
                event_type=ChatEventType.MESSAGE_RECEIVED,
                source=ChatSource.TELEGRAM,
            )

        for i in range(5):
            store.add_chat_event(
                event_id=f"evt-bedroom-{i:03d}",
                session_id=f"session-bedroom-{i:03d}",
                zone_id="zone-bedroom",
                event_type=ChatEventType.RESPONSE_GENERATED,
                source=ChatSource.WEB,
            )

        patterns = store.build_chat_patterns()

        assert isinstance(patterns, ChatPatternsV1)
        assert patterns.total_entries == 2
        assert len(patterns.patterns) == 2

    def test_build_chat_patterns_with_mixed_events(self, store: ChatAnalyticsStore) -> None:
        """Test patterns with mixed event types."""
        for i in range(8):
            store.add_chat_event(
                event_id=f"evt-msg-{i:03d}",
                session_id=f"session-{i:03d}",
                zone_id="zone-kitchen",
                event_type=ChatEventType.MESSAGE_RECEIVED,
                source=ChatSource.TELEGRAM,
            )

        for i in range(6):
            store.add_chat_event(
                event_id=f"evt-resp-{i:03d}",
                session_id=f"session-{i:03d}",
                zone_id="zone-kitchen",
                event_type=ChatEventType.RESPONSE_GENERATED,
                source=ChatSource.TELEGRAM,
            )

        for i in range(2):
            store.add_chat_event(
                event_id=f"evt-rag-{i:03d}",
                session_id=f"session-{i:03d}",
                zone_id="zone-kitchen",
                event_type=ChatEventType.RAG_RETRIEVAL,
                source=ChatSource.TELEGRAM,
            )

        patterns = store.build_chat_patterns()

        kitchen = next(p for p in patterns.patterns if p.zone_id == "zone-kitchen")
        assert kitchen.total_events == 16
        assert kitchen.messages_received == 8
        assert kitchen.responses_generated == 6
        assert kitchen.rag_retrievals == 2

    def test_get_effectiveness_metrics(self, store: ChatAnalyticsStore) -> None:
        """Test effectiveness metrics calculation."""
        for i in range(70):
            store.add_chat_event(
                event_id=f"evt-msg-{i:03d}",
                session_id=f"session-{i:03d}",
                zone_id=f"zone-{i % 5}",
                event_type=ChatEventType.MESSAGE_RECEIVED,
                source=ChatSource.TELEGRAM if i % 2 == 0 else ChatSource.WEB,
            )

        for i in range(50):
            store.add_chat_event(
                event_id=f"evt-resp-{i:03d}",
                session_id=f"session-{i:03d}",
                zone_id=f"zone-{i % 5}",
                event_type=ChatEventType.RESPONSE_GENERATED,
                source=ChatSource.TELEGRAM if i % 2 == 0 else ChatSource.WEB,
            )

        for i in range(10):
            store.add_chat_event(
                event_id=f"evt-error-{i:03d}",
                session_id=f"session-{i:03d}",
                zone_id=f"zone-{i % 3}",
                event_type=ChatEventType.ERROR_OCCURRED,
                source=ChatSource.TELEGRAM,
            )

        metrics = store.get_effectiveness_metrics()

        assert isinstance(metrics, ChatEffectivenessMetricsV1)
        assert metrics.total_sessions == 70
        assert metrics.total_events == 130
        assert metrics.zones_with_activity == 5
        assert abs(metrics.response_rate - (50 / 130)) < 0.01
        assert abs(metrics.error_rate - (10 / 130)) < 0.01
        assert "telegram" in metrics.sources_active or "web" in metrics.sources_active

    def test_build_summary(self, store: ChatAnalyticsStore) -> None:
        """Test building complete summary."""
        for i in range(5):
            store.add_chat_event(
                event_id=f"evt-{i:03d}",
                session_id=f"session-{i:03d}",
                zone_id="zone-living",
                event_type=ChatEventType.MESSAGE_RECEIVED,
                source=ChatSource.TELEGRAM,
            )

        summary = store.build_summary()

        assert summary.history is not None
        assert summary.patterns is not None
        assert summary.effectiveness is not None
        assert summary.revision == 5

    def test_build_summary_with_revision_filter(self, store: ChatAnalyticsStore) -> None:
        """Test summary with revision filter."""
        for i in range(10):
            store.add_chat_event(
                event_id=f"evt-{i:03d}",
                session_id=f"session-{i:03d}",
                zone_id="zone-living",
                event_type=ChatEventType.MESSAGE_RECEIVED,
                source=ChatSource.TELEGRAM,
            )

        summary = store.build_summary(since_revision=7)

        assert summary.history.total_count == 3
        assert summary.revision >= 10


class TestChatEventType:
    """Test ChatEventType enum."""

    def test_all_event_types(self) -> None:
        """Test all event type values."""
        assert ChatEventType.MESSAGE_RECEIVED.value == "message_received"
        assert ChatEventType.RESPONSE_GENERATED.value == "response_generated"
        assert ChatEventType.RAG_RETRIEVAL.value == "rag_retrieval"
        assert ChatEventType.MEMORY_LOOKUP.value == "memory_lookup"
        assert ChatEventType.CONTEXT_BUILT.value == "context_built"
        assert ChatEventType.TOOL_CALLED.value == "tool_called"
        assert ChatEventType.ERROR_OCCURRED.value == "error_occurred"


class TestChatSource:
    """Test ChatSource enum."""

    def test_all_sources(self) -> None:
        """Test all source values."""
        assert ChatSource.TELEGRAM.value == "telegram"
        assert ChatSource.WEB.value == "web"
        assert ChatSource.API.value == "api"
        assert ChatSource.VOICE.value == "voice"
        assert ChatSource.INTERNAL.value == "internal"


class TestChatPatternsV1:
    """Test ChatPatternsV1 serialization."""

    def test_patterns_to_dict(self, store: ChatAnalyticsStore) -> None:
        """Test patterns serialization."""
        store.add_chat_event(
            event_id="evt-001",
            session_id="session-001",
            zone_id="zone-test",
            event_type=ChatEventType.MESSAGE_RECEIVED,
            source=ChatSource.TELEGRAM,
        )

        patterns = store.build_chat_patterns()
        d = patterns.to_dict()

        assert "patterns" in d
        assert "total_entries" in d
        assert "revision" in d
        assert "generated_at" in d
        assert len(d["patterns"]) == 1


class TestChatEffectivenessMetricsV1:
    """Test ChatEffectivenessMetricsV1."""

    def test_metrics_to_dict(self, store: ChatAnalyticsStore) -> None:
        """Test metrics serialization."""
        store.add_chat_event(
            event_id="evt-001",
            session_id="session-001",
            zone_id="zone-test",
            event_type=ChatEventType.MESSAGE_RECEIVED,
            source=ChatSource.TELEGRAM,
        )

        metrics = store.get_effectiveness_metrics()
        d = metrics.to_dict()

        assert "total_sessions" in d
        assert "total_events" in d
        assert "response_rate" in d
        assert "rag_usage_rate" in d
        assert "memory_usage_rate" in d
        assert "tool_call_rate" in d
        assert "error_rate" in d
        assert "sources_active" in d
