"""Query Metrics API — Slice 65.

API-Endpoints für Query-Performance-Monitoring:
- GET /api/v1/metrics/queries — Query-Metriken-Übersicht
- GET /api/v1/metrics/queries/<query_hash> — Detail-Metriken
- POST /api/v1/metrics/queries/cache/clear — Cache leeren
- GET /api/v1/metrics/queries/indexes/recommend — Index-Empfehlungen
- POST /api/v1/metrics/queries/indexes/apply — Indexes anwenden
- GET /api/v1/metrics/queries/slow — Slow Query Report
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

from ...config import get_config
from ...performance.query_optimizer import (
    QueryOptimizer,
    QueryPattern,
    get_query_optimizer,
)

bp = Blueprint("query_metrics", __name__, url_prefix="/api/v1/metrics/queries")


def _get_optimizer() -> QueryOptimizer:
    """Query-Optimizer Instanz holen."""
    return get_query_optimizer()


def _get_db_path() -> Path:
    """Datenpfad aus Config holen."""
    try:
        cfg = get_config()
        return Path(cfg.data_dir)
    except (ImportError, AttributeError):
        return Path("/config/clawd/data")


@bp.route("", methods=["GET"])
def get_query_metrics() -> Response:
    """Query-Metriken-Übersicht abrufen.

    Query Parameters:
    - limit: Maximal zurückzugebende Queries (default: 50)
    - pattern: Filter nach Query-Pattern (optional)
    - slow_only: Nur Slow Queries zurückgeben (default: false)

    Returns:
    - JSON mit Query-Metriken-Liste und Summary
    """
    limit = request.args.get("limit", 50, type=int)
    pattern_filter = request.args.get("pattern", None)
    slow_only = request.args.get("slow_only", "false").lower() == "true"

    optimizer = _get_optimizer()
    summary = optimizer.get_metrics_summary()

    all_metrics = list(optimizer._metrics.values())

    # Filter nach Pattern
    if pattern_filter:
        try:
            pattern_enum = QueryPattern(pattern_filter)
            all_metrics = [m for m in all_metrics if m.query_pattern == pattern_enum]
        except ValueError:
            pass

    # Filter nach Slow Queries
    if slow_only:
        all_metrics = [m for m in all_metrics if m.avg_duration_ms > optimizer.SLOW_QUERY_THRESHOLD_MS]

    # Sortieren nach Execution Count
    all_metrics.sort(key=lambda m: m.execution_count, reverse=True)
    all_metrics = all_metrics[:limit]

    return jsonify({
        "summary": {
            "total_queries_tracked": summary.total_queries_tracked,
            "slow_queries_count": summary.slow_queries_count,
            "cache_hit_rate": round(summary.cache_hit_rate, 3),
            "avg_query_duration_ms": round(summary.avg_query_duration_ms, 2),
            "p95_query_duration_ms": round(summary.p95_query_duration_ms, 2),
            "generated_at": summary.generated_at,
        },
        "queries": [m.to_dict() for m in all_metrics],
        "index_recommendations": [
            {
                "table": r.table_name,
                "index_name": r.index_name,
                "columns": r.columns,
                "reason": r.reason,
                "estimated_improvement": r.estimated_improvement,
            }
            for r in summary.index_recommendations
        ],
    })


@bp.route("/<query_hash>", methods=["GET"])
def get_query_detail(query_hash: str) -> Response:
    """Detail-Metriken für spezifische Query abrufen."""
    optimizer = _get_optimizer()

    if query_hash not in optimizer._metrics:
        return jsonify({"error": f"Query hash '{query_hash}' not found"}), 404

    metrics = optimizer._metrics[query_hash]
    return jsonify(metrics.to_dict())


@bp.route("/cache/clear", methods=["POST"])
def clear_cache() -> Response:
    """Cache leeren.

    Query Parameters:
    - pattern: Nur Cache für spezifisches Pattern leeren (optional)
    - expired_only: Nur abgelaufene Einträge entfernen (default: false)

    Returns:
    - JSON mit Anzahl gelöschter Einträge
    """
    pattern_filter = request.args.get("pattern", None)
    expired_only = request.args.get("expired_only", "false").lower() == "true"

    optimizer = _get_optimizer()

    if expired_only:
        count = optimizer.cleanup_expired_cache()
    elif pattern_filter:
        try:
            pattern = QueryPattern(pattern_filter)
            count = optimizer.clear_cache(pattern)
        except ValueError:
            count = 0
    else:
        count = optimizer.clear_cache()

    return jsonify({
        "cleared_entries": count,
        "pattern": pattern_filter,
        "expired_only": expired_only,
    })


@bp.route("/indexes/recommend", methods=["GET"])
def recommend_indexes() -> Response:
    """Index-Empfehlungen generieren.

    Returns:
    - JSON mit Index-Empfehlungen für alle Analytics-Tabellen
    """
    optimizer = _get_optimizer()
    recommendations = optimizer.recommend_indexes(sqlite3.connect(":memory:"))

    return jsonify({
        "recommendations": [
            {
                "table": r.table_name,
                "index_name": r.index_name,
                "columns": r.columns,
                "reason": r.reason,
                "estimated_improvement": r.estimated_improvement,
                "create_statement": r.create_statement,
            }
            for r in recommendations
        ],
        "total_count": len(recommendations),
    })


@bp.route("/indexes/apply", methods=["POST"])
def apply_indexes() -> Response:
    """Empfohlene Composite-Indexes anwenden.

    Body (optional):
    - db_path: Pfad zur SQLite-Datenbank (default: aus Config)

    Returns:
    - JSON mit angewendeten Indexes und Fehlern
    """
    data = request.get_json(silent=True) or {}
    db_path = data.get("db_path")

    if not db_path:
        db_path = str(_get_db_path() / "analytics" / "analytics.db")

    optimizer = _get_optimizer()
    result = optimizer.apply_recommended_indexes(db_path)

    status_code = 200 if not result.get("errors") else 207

    return jsonify(result), status_code


@bp.route("/slow", methods=["GET"])
def get_slow_queries() -> Response:
    """Slow Query Report abrufen.

    Query Parameters:
    - threshold_ms: Schwellwert für Slow Queries (default: 50ms)
    - limit: Maximale Anzahl zurückgegebener Queries (default: 20)

    Returns:
    - JSON mit Slow Query-Liste und Analyse
    """
    threshold_ms = request.args.get("threshold_ms", 50.0, type=float)
    limit = request.args.get("limit", 20, type=int)

    optimizer = _get_optimizer()
    summary = optimizer.get_metrics_summary()

    # Überschreiben des Thresholds für diesen Report
    slow_queries = [
        m for m in optimizer._metrics.values()
        if m.avg_duration_ms > threshold_ms
    ]
    slow_queries.sort(key=lambda m: m.avg_duration_ms, reverse=True)
    slow_queries = slow_queries[:limit]

    return jsonify({
        "threshold_ms": threshold_ms,
        "slow_queries_count": len(slow_queries),
        "queries": [m.to_dict() for m in slow_queries],
        "recommendations": [
            "Composite Indexes für multi-column WHERE clauses hinzufügen",
            "Query-Cache-TTL für häufige Analytics-Queries erhöhen",
            "EXPLAIN QUERY PLAN für einzelne Queries zur Index-Analyse nutzen",
        ],
    })


@bp.route("/analyze", methods=["POST"])
def analyze_query() -> Response:
    """Query-Plan für spezifische Query analysieren.

    Body:
    - query: SQL-Query-String (required)
    - params: Query-Parameter als Array (optional)
    - db_path: Pfad zur Datenbank (optional, default: analytics.db)

    Returns:
    - JSON mit Query-Plan-Analyse (Table Scans, Index Usage)
    """
    data = request.get_json() or {}
    query = data.get("query")

    if not query:
        return jsonify({"error": "query parameter required"}), 400

    params = tuple(data.get("params", []))
    db_path = data.get("db_path", str(_get_db_path() / "analytics" / "analytics.db"))

    optimizer = _get_optimizer()

    try:
        conn = sqlite3.connect(db_path)
        plan = optimizer.analyze_query_plan(conn, query, params)
        conn.close()

        return jsonify(plan)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/batch", methods=["POST"])
def batch_operation() -> Response:
    """Batch-Insert/Update Operation ausführen.

    Body:
    - operation: "insert" oder "update" (required)
    - table: Tabellenname (required)
    - columns: Spaltennamen für Insert (required für insert)
    - rows: Datenreihen als Array von Arrays (required)
    - set_clause: SET-Clause für Update (required für update)
    - where_clause: WHERE-Clause für Update (required für update)
    - chunk_size: Chunk-Größe für Batch (default: 100)
    - db_path: Pfad zur Datenbank (optional)

    Returns:
    - JSON mit Anzahl betroffener Zeilen
    """
    data = request.get_json() or {}
    operation = data.get("operation")
    table = data.get("table")
    rows = data.get("rows", [])

    if not operation or not table or not rows:
        return jsonify({"error": "operation, table, and rows required"}), 400

    db_path = data.get("db_path", str(_get_db_path() / "analytics" / "analytics.db"))
    optimizer = _get_optimizer()

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")

        if operation == "insert":
            columns = data.get("columns", [])
            if not columns:
                return jsonify({"error": "columns required for insert"}), 400
            chunk_size = data.get("chunk_size", 100)
            count = optimizer.batch_insert(conn, table, columns, rows, chunk_size)
        elif operation == "update":
            set_clause = data.get("set_clause")
            where_clause = data.get("where_clause")
            if not set_clause or not where_clause:
                return jsonify({"error": "set_clause and where_clause required for update"}), 400
            count = optimizer.batch_update(conn, table, set_clause, where_clause, rows)
        else:
            return jsonify({"error": "operation must be 'insert' or 'update'"}), 400

        conn.close()

        return jsonify({
            "operation": operation,
            "table": table,
            "rows_affected": count,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def create_blueprint() -> Blueprint:
    """Blueprint für Query-Metrics-API erstellen."""
    return bp
