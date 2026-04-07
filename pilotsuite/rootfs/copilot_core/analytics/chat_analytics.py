"""Chat/RAG Analytics Surface — Slice 62."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ChatEventType(str, Enum):
    """Chat event types."""
    MESSAGE_RECEIVED = "message_received"
    RESPONSE_GENERATED = "response_generated"
    RAG_RETRIEVAL = "rag_retrieval"
    MEMORY_LOOKUP = "memory_lookup"
    CONTEXT_BUILT = "context_built"
    TOOL_CALLED = "tool_called"
    ERROR_OCCURRED = "error_occurred"


class ChatSource(str, Enum):
    """Chat source types."""
    TELEGRAM = "telegram"
    WEB = "web"
    API = "api"
    VOICE = "voice"
    INTERNAL = "internal"


@dataclass
class ChatEventV1:
    """Single chat/RAG event."""
    event_id: str
    session_id: str | None
    zone_id: str | None
    event_type: ChatEventType
    source: ChatSource
    timestamp: float
    revision: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "zone_id": self.zone_id,
            "event_type": self.event_type.value,
            "source": self.source.value,
            "timestamp": self.timestamp,
            "revision": self.revision,
            "metadata": self.metadata,
        }


@dataclass
class ChatHistoryV1:
    """Chat event history."""
    events: list[ChatEventV1]
    total_count: int
    from_timestamp: float | None
    to_timestamp: float | None
    revision: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self.events],
            "total_count": self.total_count,
            "from_timestamp": self.from_timestamp,
            "to_timestamp": self.to_timestamp,
            "revision": self.revision,
        }


@dataclass
class ChatPatternEntryV1:
    """Chat pattern entry for a specific zone/source."""
    zone_id: str | None
    zone_name: str | None
    source: ChatSource
    total_events: int
    messages_received: int
    responses_generated: int
    rag_retrievals: int
    memory_lookups: int
    tool_calls: int
    errors: int
    events_per_day: float
    last_event_at: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "source": self.source.value,
            "total_events": self.total_events,
            "messages_received": self.messages_received,
            "responses_generated": self.responses_generated,
            "rag_retrievals": self.rag_retrievals,
            "memory_lookups": self.memory_lookups,
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "events_per_day": self.events_per_day,
            "last_event_at": self.last_event_at,
        }


@dataclass
class ChatPatternsV1:
    """Chat-specific patterns."""
    patterns: list[ChatPatternEntryV1]
    total_entries: int
    revision: int
    generated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "patterns": [p.to_dict() for p in self.patterns],
            "total_entries": self.total_entries,
            "revision": self.revision,
            "generated_at": self.generated_at,
        }


@dataclass
class ChatEffectivenessMetricsV1:
    """Chat effectiveness metrics."""
    total_sessions: int
    total_events: int
    response_rate: float
    rag_usage_rate: float
    memory_usage_rate: float
    tool_call_rate: float
    error_rate: float
    avg_events_per_session: float
    zones_with_activity: int
    sources_active: list[str]
    revision: int
    generated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_sessions": self.total_sessions,
            "total_events": self.total_events,
            "response_rate": self.response_rate,
            "rag_usage_rate": self.rag_usage_rate,
            "memory_usage_rate": self.memory_usage_rate,
            "tool_call_rate": self.tool_call_rate,
            "error_rate": self.error_rate,
            "avg_events_per_session": self.avg_events_per_session,
            "zones_with_activity": self.zones_with_activity,
            "sources_active": self.sources_active,
            "revision": self.revision,
            "generated_at": self.generated_at,
        }


@dataclass
class ChatAnalyticsSummaryV1:
    """Chat analytics summary."""
    history: ChatHistoryV1 | None
    patterns: ChatPatternsV1 | None
    effectiveness: ChatEffectivenessMetricsV1 | None
    revision: int
    generated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "history": self.history.to_dict() if self.history else None,
            "patterns": self.patterns.to_dict() if self.patterns else None,
            "effectiveness": self.effectiveness.to_dict() if self.effectiveness else None,
            "revision": self.revision,
            "generated_at": self.generated_at,
        }


class ChatAnalyticsStore:
    """SQLite-backed chat/RAG analytics store."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._revision = 0

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS chat_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    zone_id TEXT,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    revision INTEGER NOT NULL,
                    metadata_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_chat_events_session_id
                    ON chat_events(session_id);
                CREATE INDEX IF NOT EXISTS idx_chat_events_timestamp
                    ON chat_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_chat_events_type
                    ON chat_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_chat_events_source
                    ON chat_events(source);
                CREATE INDEX IF NOT EXISTS idx_chat_events_zone
                    ON chat_events(zone_id);
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_next_revision(self) -> int:
        """Get next revision number."""
        self._revision += 1
        return self._revision

    def add_chat_event(
        self,
        event_id: str,
        session_id: str | None,
        zone_id: str | None,
        event_type: ChatEventType,
        source: ChatSource,
        metadata: dict[str, Any] | None = None,
    ) -> ChatEventV1:
        """Record a chat event."""
        timestamp = time.time()
        revision = self._get_next_revision()

        entry = ChatEventV1(
            event_id=event_id,
            session_id=session_id,
            zone_id=zone_id,
            event_type=event_type,
            source=source,
            timestamp=timestamp,
            revision=revision,
            metadata=metadata or {},
        )

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """
                INSERT INTO chat_events
                (event_id, session_id, zone_id, event_type, source,
                 timestamp, revision, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.event_id,
                    entry.session_id,
                    entry.zone_id,
                    entry.event_type.value,
                    entry.source.value,
                    entry.timestamp,
                    entry.revision,
                    json.dumps(entry.metadata),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return entry

    def build_chat_history(
        self,
        session_id: str | None = None,
        zone_id: str | None = None,
        event_type: ChatEventType | None = None,
        source: ChatSource | None = None,
        from_timestamp: float | None = None,
        to_timestamp: float | None = None,
        limit: int = 100,
        since_revision: int | None = None,
    ) -> ChatHistoryV1:
        """Build chat history with filters."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            query = "SELECT * FROM chat_events WHERE 1=1"
            params: list[Any] = []

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)
            if zone_id:
                query += " AND zone_id = ?"
                params.append(zone_id)
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value)
            if source:
                query += " AND source = ?"
                params.append(source.value)
            if from_timestamp:
                query += " AND timestamp >= ?"
                params.append(from_timestamp)
            if to_timestamp:
                query += " AND timestamp <= ?"
                params.append(to_timestamp)
            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            count_query = query.replace("SELECT *", "SELECT COUNT(*)").replace(
                "ORDER BY timestamp DESC LIMIT ?", ""
            )
            count_params = params[:-1]
            total_count = conn.execute(count_query, count_params).fetchone()[0]

            max_revision = conn.execute(
                "SELECT MAX(revision) FROM chat_events"
            ).fetchone()[0] or 0
        finally:
            conn.close()

        events = []
        for row in rows:
            events.append(
                ChatEventV1(
                    event_id=row[0],
                    session_id=row[1],
                    zone_id=row[2],
                    event_type=ChatEventType(row[3]),
                    source=ChatSource(row[4]),
                    timestamp=row[5],
                    revision=row[6],
                    metadata=json.loads(row[7]) if row[7] else {},
                )
            )

        return ChatHistoryV1(
            events=list(reversed(events)),
            total_count=total_count,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            revision=max_revision,
        )

    def build_chat_patterns(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> ChatPatternsV1:
        """Build chat-specific patterns by zone and source."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cutoff = time.time() - (days_lookback * 24 * 60 * 60)

            query = """
                SELECT
                    zone_id,
                    source,
                    COUNT(*) as total_events,
                    SUM(CASE WHEN event_type = 'message_received' THEN 1 ELSE 0 END) as messages_received,
                    SUM(CASE WHEN event_type = 'response_generated' THEN 1 ELSE 0 END) as responses_generated,
                    SUM(CASE WHEN event_type = 'rag_retrieval' THEN 1 ELSE 0 END) as rag_retrievals,
                    SUM(CASE WHEN event_type = 'memory_lookup' THEN 1 ELSE 0 END) as memory_lookups,
                    SUM(CASE WHEN event_type = 'tool_called' THEN 1 ELSE 0 END) as tool_calls,
                    SUM(CASE WHEN event_type = 'error_occurred' THEN 1 ELSE 0 END) as errors,
                    MAX(timestamp) as last_event_at
                FROM chat_events
                WHERE timestamp >= ?
            """
            params: list[Any] = [cutoff]

            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)

            query += " GROUP BY zone_id, source"

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            max_revision = conn.execute(
                "SELECT MAX(revision) FROM chat_events"
            ).fetchone()[0] or 0

            patterns = []
            for row in rows:
                zone_id, source, total, messages, responses, rag, memory, tools, errors, last_ts = row

                total = total or 0
                messages = messages or 0
                responses = responses or 0
                rag = rag or 0
                memory = memory or 0
                tools = tools or 0
                errors = errors or 0

                if total > 1 and last_ts:
                    first_ts = conn.execute(
                        "SELECT MIN(timestamp) FROM chat_events WHERE zone_id = ? AND source = ? AND timestamp >= ?",
                        (zone_id, source, cutoff),
                    ).fetchone()[0]
                    if first_ts and last_ts > first_ts:
                        days_span = max(1, (last_ts - first_ts) / (24 * 60 * 60))
                        freq = total / days_span
                    else:
                        freq = 0.0
                else:
                    freq = 0.0

                patterns.append(
                    ChatPatternEntryV1(
                        zone_id=zone_id,
                        zone_name=None,
                        source=ChatSource(source),
                        total_events=total,
                        messages_received=messages,
                        responses_generated=responses,
                        rag_retrievals=rag,
                        memory_lookups=memory,
                        tool_calls=tools,
                        errors=errors,
                        events_per_day=freq,
                        last_event_at=last_ts,
                    )
                )

            return ChatPatternsV1(
                patterns=patterns,
                total_entries=len(patterns),
                revision=max_revision,
                generated_at=time.time(),
            )
        finally:
            conn.close()

    def get_effectiveness_metrics(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> ChatEffectivenessMetricsV1:
        """Calculate chat effectiveness metrics."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cutoff = time.time() - (days_lookback * 24 * 60 * 60)

            query = """
                SELECT
                    COUNT(DISTINCT session_id) as total_sessions,
                    COUNT(*) as total_events,
                    SUM(CASE WHEN event_type = 'response_generated' THEN 1 ELSE 0 END) as responses,
                    SUM(CASE WHEN event_type = 'rag_retrieval' THEN 1 ELSE 0 END) as rag,
                    SUM(CASE WHEN event_type = 'memory_lookup' THEN 1 ELSE 0 END) as memory,
                    SUM(CASE WHEN event_type = 'tool_called' THEN 1 ELSE 0 END) as tools,
                    SUM(CASE WHEN event_type = 'error_occurred' THEN 1 ELSE 0 END) as errors,
                    COUNT(DISTINCT zone_id) as zones_with_activity
                FROM chat_events
                WHERE timestamp >= ?
            """
            params: list[Any] = [cutoff]

            if since_revision:
                query += " AND revision > ?"
                params.append(since_revision)

            row = conn.execute(query, params).fetchone()
            (
                total_sessions,
                total_events,
                responses,
                rag,
                memory,
                tools,
                errors,
                zones_with_activity,
            ) = row

            total_sessions = total_sessions or 0
            total_events = total_events or 0
            responses = responses or 0
            rag = rag or 0
            memory = memory or 0
            tools = tools or 0
            errors = errors or 0
            zones_with_activity = zones_with_activity or 0

            response_rate = (responses / total_events) if total_events > 0 else 0.0
            rag_usage_rate = (rag / total_events) if total_events > 0 else 0.0
            memory_usage_rate = (memory / total_events) if total_events > 0 else 0.0
            tool_call_rate = (tools / total_events) if total_events > 0 else 0.0
            error_rate = (errors / total_events) if total_events > 0 else 0.0
            avg_events_per_session = (total_events / total_sessions) if total_sessions > 0 else 0.0

            source_query = """
                SELECT DISTINCT source FROM chat_events
                WHERE timestamp >= ?
            """
            source_params: list[Any] = [cutoff]
            if since_revision:
                source_query += " AND revision > ?"
                source_params.append(since_revision)

            sources_active = [row[0] for row in conn.execute(source_query, source_params) if row[0]]

            max_revision = conn.execute(
                "SELECT MAX(revision) FROM chat_events"
            ).fetchone()[0] or 0
        finally:
            conn.close()

        return ChatEffectivenessMetricsV1(
            total_sessions=total_sessions,
            total_events=total_events,
            response_rate=response_rate,
            rag_usage_rate=rag_usage_rate,
            memory_usage_rate=memory_usage_rate,
            tool_call_rate=tool_call_rate,
            error_rate=error_rate,
            avg_events_per_session=avg_events_per_session,
            zones_with_activity=zones_with_activity,
            sources_active=sources_active,
            revision=max_revision,
            generated_at=time.time(),
        )

    def build_summary(
        self,
        days_lookback: int = 30,
        since_revision: int | None = None,
    ) -> ChatAnalyticsSummaryV1:
        """Build complete chat analytics summary."""
        history = self.build_chat_history(
            from_timestamp=time.time() - (days_lookback * 24 * 60 * 60),
            limit=50,
            since_revision=since_revision,
        )
        patterns = self.build_chat_patterns(
            days_lookback=days_lookback,
            since_revision=since_revision,
        )
        effectiveness = self.get_effectiveness_metrics(
            days_lookback=days_lookback,
            since_revision=since_revision,
        )

        max_revision = max(
            history.revision,
            patterns.revision,
            effectiveness.revision,
        )

        return ChatAnalyticsSummaryV1(
            history=history,
            patterns=patterns,
            effectiveness=effectiveness,
            revision=max_revision,
            generated_at=time.time(),
        )
