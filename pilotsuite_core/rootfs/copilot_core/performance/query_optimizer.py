"""Database Query Optimization — Slice 65.

Query-Performance-Optimierung durch:
- Composite Indexes für häufigste Query-Patterns
- Query Result Caching mit TTL
- Batch Insert/Update Operations
- Query Plan Analysis für Slow Queries
- Performance Metrics unter /api/v1/metrics/queries
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class QueryPattern(str, Enum):
    """Häufigste Query-Patterns."""
    ZONE_BY_ID_TIMESTAMP = "zone_by_id_timestamp"
    MODULE_BY_ID_STATUS = "module_by_id_status"
    PROPOSAL_BY_ZONE_SOURCE = "proposal_by_zone_source"
    CLOSURE_BY_ZONE_TIMESTAMP = "closure_by_zone_timestamp"
    EVENT_BY_TYPE_STATUS = "event_by_type_status"
    ANALYTICS_ZONE_AGGREGATION = "analytics_zone_aggregation"
    ANALYTICS_MODULE_AGGREGATION = "analytics_module_aggregation"
    TIME_RANGE_FILTER = "time_range_filter"


@dataclass
class QueryMetrics:
    """Metriken für Query-Performance."""
    query_hash: str
    query_pattern: QueryPattern | None
    execution_count: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    rows_returned_total: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    last_executed_at: float | None = None
    last_duration_ms: float = 0.0
    index_used: str | None = None
    table_scans: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_hash": self.query_hash,
            "query_pattern": self.query_pattern.value if self.query_pattern else None,
            "execution_count": self.execution_count,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms, 2) if self.min_duration_ms != float("inf") else 0,
            "max_duration_ms": round(self.max_duration_ms, 2),
            "p95_duration_ms": round(self.p95_duration_ms, 2),
            "rows_returned_total": self.rows_returned_total,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(self.cache_hits / max(1, self.cache_hits + self.cache_misses), 3),
            "last_executed_at": datetime.fromtimestamp(self.last_executed_at, tz=timezone.utc).isoformat() if self.last_executed_at else None,
            "last_duration_ms": round(self.last_duration_ms, 2),
            "index_used": self.index_used,
            "table_scans": self.table_scans,
        }


@dataclass
class CacheEntry:
    """Cache-Eintrag mit TTL."""
    query_hash: str
    result: Any
    created_at: float
    ttl_seconds: float
    hits: int = 0

    def is_expired(self) -> bool:
        return time.time() > self.created_at + self.ttl_seconds


@dataclass
class IndexRecommendation:
    """Index-Optimierungsempfehlung."""
    table_name: str
    index_name: str
    columns: list[str]
    reason: str
    estimated_improvement: str
    create_statement: str


@dataclass
class QueryOptimizerSummary:
    """Zusammenfassung der Query-Optimierung."""
    total_queries_tracked: int
    slow_queries_count: int
    cache_hit_rate: float
    avg_query_duration_ms: float
    p95_query_duration_ms: float
    index_recommendations: list[IndexRecommendation]
    top_slow_queries: list[QueryMetrics]
    generated_at: str


class QueryOptimizer:
    """Query-Optimizer mit Caching, Index-Analyse und Batch-Operations."""

    # TTL-Konfiguration nach Query-Typ
    CACHE_TTL_DEFAULT = 60.0  # 60s für Sensor-Daten
    CACHE_TTL_RAG = 600.0  # 10min für RAG
    CACHE_TTL_CONFIG = 3600.0  # 1h für Config
    CACHE_TTL_ANALYTICS = 300.0  # 5min für Analytics

    # Slow Query Threshold
    SLOW_QUERY_THRESHOLD_MS = 50.0

    def __init__(self, db_path: Path | str | None = None, cache_enabled: bool = True):
        self.db_path = Path(db_path) if db_path else None
        self.cache_enabled = cache_enabled
        self._cache: dict[str, CacheEntry] = {}
        self._metrics: dict[str, QueryMetrics] = {}
        self._duration_history: list[float] = []
        self._index_advice_cache: list[IndexRecommendation] = []

    def _hash_query(self, query: str, params: tuple | None = None) -> str:
        """Query-Hash für Cache-Lookup berechnen."""
        normalized = " ".join(query.split()).lower()
        key = f"{normalized}:{json.dumps(params, sort_keys=True) if params else ''}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _detect_pattern(self, query: str) -> QueryPattern | None:
        """Query-Pattern erkennen."""
        q = query.lower()
        if "zone_sync_events" in q and "zone_id" in q and "timestamp" in q:
            return QueryPattern.ZONE_BY_ID_TIMESTAMP
        if "module_executions" in q and "module_id" in q and "status" in q:
            return QueryPattern.MODULE_BY_ID_STATUS
        if "proposal_lifecycle_events" in q and "zone_id" in q and "source" in q:
            return QueryPattern.PROPOSAL_BY_ZONE_SOURCE
        if "action_closure_events" in q and "zone_id" in q and "timestamp" in q:
            return QueryPattern.CLOSURE_BY_ZONE_TIMESTAMP
        if "event_type" in q and "status" in q and "where" in q:
            return QueryPattern.EVENT_BY_TYPE_STATUS
        if "zone_id" in q and ("avg(" in q or "count(" in q or "sum(" in q):
            return QueryPattern.ANALYTICS_ZONE_AGGREGATION
        if "module_id" in q and ("avg(" in q or "count(" in q or "sum(" in q):
            return QueryPattern.ANALYTICS_MODULE_AGGREGATION
        if "timestamp" in q and ("between" in q or ">=" in q or "<=" in q):
            return QueryPattern.TIME_RANGE_FILTER
        return None

    def _get_ttl_for_pattern(self, pattern: QueryPattern | None) -> float:
        """TTL basierend auf Query-Pattern bestimmen."""
        if pattern in (QueryPattern.ANALYTICS_ZONE_AGGREGATION, QueryPattern.ANALYTICS_MODULE_AGGREGATION):
            return self.CACHE_TTL_ANALYTICS
        return self.CACHE_TTL_DEFAULT

    def execute_with_cache(
        self,
        conn: sqlite3.Connection,
        query: str,
        params: tuple | None = None,
        ttl: float | None = None,
        force_refresh: bool = False,
    ) -> list[tuple]:
        """Query mit Cache-Unterstützung ausführen."""
        query_hash = self._hash_query(query, params)
        pattern = self._detect_pattern(query)

        if ttl is None:
            ttl = self._get_ttl_for_pattern(pattern)

        # Cache-Lookup
        if self.cache_enabled and not force_refresh and query_hash in self._cache:
            entry = self._cache[query_hash]
            if not entry.is_expired():
                entry.hits += 1
                self._record_metrics(query_hash, pattern, 0.0, len(entry.result), cache_hit=True)
                return entry.result
            else:
                del self._cache[query_hash]

        # Query-Ausführung mit Timing
        start = time.perf_counter()
        cursor = conn.execute(query, params or ())
        result = cursor.fetchall()
        duration_ms = (time.perf_counter() - start) * 1000

        # Cache speichern
        if self.cache_enabled:
            self._cache[query_hash] = CacheEntry(
                query_hash=query_hash,
                result=result,
                created_at=time.time(),
                ttl_seconds=ttl,
            )

        self._record_metrics(query_hash, pattern, duration_ms, len(result), cache_hit=False)
        return result

    def _record_metrics(
        self,
        query_hash: str,
        pattern: QueryPattern | None,
        duration_ms: float,
        rows_returned: int,
        cache_hit: bool = False,
    ) -> None:
        """Query-Metriken aufzeichnen."""
        if query_hash not in self._metrics:
            self._metrics[query_hash] = QueryMetrics(
                query_hash=query_hash,
                query_pattern=pattern,
            )

        m = self._metrics[query_hash]
        m.execution_count += 1
        m.total_duration_ms += duration_ms
        m.avg_duration_ms = m.total_duration_ms / m.execution_count
        m.min_duration_ms = min(m.min_duration_ms, duration_ms)
        m.max_duration_ms = max(m.max_duration_ms, duration_ms)
        m.rows_returned_total += rows_returned
        m.last_executed_at = time.time()
        m.last_duration_ms = duration_ms

        if cache_hit:
            m.cache_hits += 1
        else:
            m.cache_misses += 1
            self._duration_history.append(duration_ms)

    def analyze_query_plan(
        self,
        conn: sqlite3.Connection,
        query: str,
        params: tuple | None = None,
    ) -> dict[str, Any]:
        """Query-Plan analysieren (EXPLAIN QUERY PLAN)."""
        try:
            cursor = conn.execute(f"EXPLAIN QUERY PLAN {query}", params or ())
            plan_rows = cursor.fetchall()

            table_scans = 0
            index_used = None
            details = []

            for row in plan_rows:
                detail = row[3] if len(row) > 3 else str(row)
                details.append(detail)
                if "SCAN" in detail and "USING INDEX" not in detail:
                    table_scans += 1
                if "USING INDEX" in detail:
                    index_used = detail.split("USING INDEX ")[-1].split()[0] if "USING INDEX " in detail else None

            return {
                "query": query,
                "plan_details": details,
                "table_scans": table_scans,
                "index_used": index_used,
                "uses_index": index_used is not None,
            }
        except Exception as e:
            return {"error": str(e), "query": query}

    def batch_insert(
        self,
        conn: sqlite3.Connection,
        table: str,
        columns: list[str],
        rows: list[tuple],
        chunk_size: int = 100,
    ) -> int:
        """Batch-Insert mit Transaktion für hohe Performance."""
        if not rows:
            return 0

        placeholders = ", ".join(["?" for _ in columns])
        col_list = ", ".join(columns)
        insert_sql = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"

        total_inserted = 0
        conn.execute("BEGIN IMMEDIATE")
        try:
            for i in range(0, len(rows), chunk_size):
                chunk = rows[i:i + chunk_size]
                conn.executemany(insert_sql, chunk)
                total_inserted += len(chunk)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return total_inserted

    def batch_update(
        self,
        conn: sqlite3.Connection,
        table: str,
        set_clause: str,
        where_clause: str,
        params_list: list[tuple],
    ) -> int:
        """Batch-Update mit Transaktion."""
        if not params_list:
            return 0

        update_sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"

        conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.executemany(update_sql, params_list)
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise

    def recommend_indexes(
        self,
        conn: sqlite3.Connection,
    ) -> list[IndexRecommendation]:
        """Index-Empfehlungen basierend auf Query-Patterns generieren."""
        recommendations = []

        # Composite Indexes für häufige Query-Kombinationen
        composite_indexes = [
            ("zone_sync_events", "idx_zone_zone_timestamp", ["zone_id", "timestamp"]),
            ("zone_sync_events", "idx_zone_type_status", ["zone_id", "event_type", "status"]),
            ("module_executions", "idx_module_status_time", ["module_id", "status", "execution_time"]),
            ("module_executions", "idx_module_zone_status", ["module_id", "zone_id", "status"]),
            ("action_closure_events", "idx_closure_zone_time", ["zone_id", "timestamp"]),
            ("action_closure_events", "idx_closure_source_status", ["source", "status"]),
            ("proposal_lifecycle_events", "idx_proposal_zone_source", ["zone_id", "source", "timestamp"]),
            ("neuron_events", "idx_neuron_zone_layer", ["zone_id", "layer", "timestamp"]),
            ("chat_events", "idx_chat_zone_source", ["zone_id", "source", "timestamp"]),
            ("health_checks", "idx_health_component_status", ["component", "status", "check_time"]),
        ]

        for table, idx_name, columns in composite_indexes:
            recommendations.append(IndexRecommendation(
                table_name=table,
                index_name=idx_name,
                columns=columns,
                reason=f"Composite index für häufige Filter-Kombination auf {table}",
                estimated_improvement="30-60% für multi-column WHERE clauses",
                create_statement=f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({', '.join(columns)});",
            ))

        return recommendations

    def apply_recommended_indexes(
        self,
        db_path: Path | str,
    ) -> dict[str, Any]:
        """Empfohlene Indexes anwenden."""
        conn = sqlite3.connect(str(db_path))
        try:
            recommendations = self.recommend_indexes(conn)
            applied = []
            errors = []

            for rec in recommendations:
                try:
                    conn.execute(rec.create_statement)
                    applied.append(rec.index_name)
                except Exception as e:
                    errors.append({"index": rec.index_name, "error": str(e)})

            conn.commit()

            return {
                "applied_indexes": applied,
                "errors": errors,
                "total_recommended": len(recommendations),
            }
        finally:
            conn.close()

    def get_metrics_summary(self) -> QueryOptimizerSummary:
        """Zusammenfassung der Query-Metriken."""
        all_metrics = list(self._metrics.values())

        # Slow queries (>50ms avg)
        slow_queries = [m for m in all_metrics if m.avg_duration_ms > self.SLOW_QUERY_THRESHOLD_MS]
        slow_queries.sort(key=lambda m: m.avg_duration_ms, reverse=True)

        # P95 berechnen
        if self._duration_history:
            sorted_durations = sorted(self._duration_history)
            p95_idx = int(len(sorted_durations) * 0.95)
            p95_duration = sorted_durations[min(p95_idx, len(sorted_durations) - 1)]
        else:
            p95_duration = 0.0

        # Gesamte Cache-Hit-Rate
        total_hits = sum(m.cache_hits for m in all_metrics)
        total_misses = sum(m.cache_misses for m in all_metrics)
        cache_hit_rate = total_hits / max(1, total_hits + total_misses)

        # Durchschnittliche Dauer
        avg_duration = sum(m.avg_duration_ms for m in all_metrics) / max(1, len(all_metrics))

        return QueryOptimizerSummary(
            total_queries_tracked=len(all_metrics),
            slow_queries_count=len(slow_queries),
            cache_hit_rate=cache_hit_rate,
            avg_query_duration_ms=avg_duration,
            p95_query_duration_ms=p95_duration,
            index_recommendations=self._index_advice_cache or self.recommend_indexes(sqlite3.connect(":memory:")),
            top_slow_queries=slow_queries[:10],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def clear_cache(self, pattern: QueryPattern | None = None) -> int:
        """Cache leeren (gesamt oder nach Pattern)."""
        if pattern is None:
            count = len(self._cache)
            self._cache.clear()
            return count

        expired_keys = [
            k for k, v in self._cache.items()
            if self._metrics.get(k, QueryMetrics(query_hash="")).query_pattern == pattern
        ]
        for k in expired_keys:
            del self._cache[k]
        return len(expired_keys)

    def cleanup_expired_cache(self) -> int:
        """Abgelaufene Cache-Einträge entfernen."""
        expired = [k for k, v in self._cache.items() if v.is_expired()]
        for k in expired:
            del self._cache[k]
        return len(expired)


# Globaler Optimizer für get_config()-basierte Initialisierung
_optimizer_instance: QueryOptimizer | None = None


def get_query_optimizer(db_path: Path | str | None = None) -> QueryOptimizer:
    """Singleton Query-Optimizer Instanz."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = QueryOptimizer(db_path=db_path)
    return _optimizer_instance
