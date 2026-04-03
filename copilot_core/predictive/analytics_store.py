"""Predictive Analytics Store — Slice 48."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional

from .analytics import (
    PredictiveUsageEntryV1,
    PredictiveUsageHistoryV1,
    PredictiveZonePatternEntryV1,
    PredictiveZonePatternsV1,
    PredictiveEffectivenessMetricsV1,
    PredictiveAnalyticsSummaryV1,
    PredictiveTrendEntryV1,
    PredictiveTrendsV1,
)


class PredictiveAnalyticsStore:
    """Store for predictive analytics read models."""

    def __init__(self, db_path: str = "/data/predictive_analytics.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Usage history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictive_usage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id TEXT NOT NULL,
                pattern_id TEXT NOT NULL,
                zone_id TEXT NOT NULL,
                module_id TEXT NOT NULL,
                prediction_type TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                outcome TEXT NOT NULL,
                accepted_at TEXT,
                rejected_at TEXT,
                expired_at TEXT,
                feedback TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Zone patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictive_zone_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id TEXT UNIQUE NOT NULL,
                zone_name TEXT,
                total_proposals INTEGER NOT NULL DEFAULT 0,
                accepted_count INTEGER NOT NULL DEFAULT 0,
                rejected_count INTEGER NOT NULL DEFAULT 0,
                expired_count INTEGER NOT NULL DEFAULT 0,
                acceptance_rate REAL NOT NULL DEFAULT 0.0,
                avg_confidence_score REAL,
                most_common_prediction_type TEXT,
                last_proposal_at TEXT,
                proposals_last_7_days INTEGER NOT NULL DEFAULT 0,
                proposals_last_30_days INTEGER NOT NULL DEFAULT 0,
                dominant_pattern_ids TEXT,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Effectiveness metrics table (single row)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictive_effectiveness_metrics (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_proposals_analyzed INTEGER DEFAULT 0,
                high_confidence_proposals INTEGER DEFAULT 0,
                high_confidence_acceptance_rate REAL DEFAULT 0.0,
                low_confidence_proposals INTEGER DEFAULT 0,
                low_confidence_acceptance_rate REAL DEFAULT 0.0,
                avg_time_to_accept_minutes REAL,
                avg_time_to_reject_minutes REAL,
                pattern_reinforcement_count INTEGER DEFAULT 0,
                pattern_degradation_count INTEGER DEFAULT 0,
                seasonal_adaptation_events INTEGER DEFAULT 0,
                effectiveness_score REAL DEFAULT 0.0,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Trends table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictive_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                proposals_count INTEGER NOT NULL,
                accepted_count INTEGER NOT NULL,
                rejected_count INTEGER NOT NULL,
                avg_confidence REAL NOT NULL,
                acceptance_rate REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Initialize single-row metrics if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO predictive_effectiveness_metrics (id) VALUES (1)
        """)

        conn.commit()
        conn.close()

    def add_usage_entry(self, entry: PredictiveUsageEntryV1) -> None:
        """Add predictive usage entry."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO predictive_usage_history 
            (proposal_id, pattern_id, zone_id, module_id, prediction_type,
             confidence_score, outcome, accepted_at, rejected_at, expired_at, feedback)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.proposal_id, entry.pattern_id, entry.zone_id, entry.module_id,
            entry.prediction_type, entry.confidence_score, entry.outcome,
            entry.accepted_at, entry.rejected_at, entry.expired_at, entry.feedback
        ))

        conn.commit()
        conn.close()

    def build_usage_history(
        self,
        time_range_start: Optional[str] = None,
        time_range_end: Optional[str] = None,
        zone_id: Optional[str] = None,
        prediction_type: Optional[str] = None,
        since_revision: Optional[int] = None
    ) -> PredictiveUsageHistoryV1:
        """Build usage history read model."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build query
        query = """
            SELECT proposal_id, pattern_id, zone_id, module_id,
                   prediction_type, confidence_score, outcome,
                   accepted_at, rejected_at, expired_at, feedback, created_at
            FROM predictive_usage_history
            WHERE 1=1
        """
        params = []

        if time_range_start:
            query += " AND created_at >= ?"
            params.append(time_range_start)
        if time_range_end:
            query += " AND created_at <= ?"
            params.append(time_range_end)
        if zone_id:
            query += " AND zone_id = ?"
            params.append(zone_id)
        if prediction_type:
            query += " AND prediction_type = ?"
            params.append(prediction_type)

        if since_revision:
            query += " ORDER BY created_at DESC LIMIT 100"
        else:
            query += " ORDER BY created_at ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        # Build read model
        entries = []
        total_proposals = 0
        total_accepted = 0
        total_rejected = 0
        total_expired = 0
        total_pending = 0
        confidence_sum = 0.0
        latest_change_at = datetime.now(timezone.utc).isoformat()

        for row in rows:
            entry = PredictiveUsageEntryV1(
                proposal_id=row[0],
                pattern_id=row[1],
                zone_id=row[2],
                module_id=row[3],
                prediction_type=row[4],
                confidence_score=row[5],
                outcome=row[6],
                accepted_at=row[7],
                rejected_at=row[8],
                expired_at=row[9],
                feedback=row[10],
                created_at=row[11],
            )
            entries.append(entry)
            total_proposals += 1
            confidence_sum += row[5]

            if row[6] == "accepted":
                total_accepted += 1
            elif row[6] == "rejected":
                total_rejected += 1
            elif row[6] == "expired":
                total_expired += 1
            else:
                total_pending += 1

            if row[11]:
                latest_change_at = row[11]

        acceptance_rate = total_accepted / total_proposals if total_proposals > 0 else 0.0
        avg_confidence = confidence_sum / total_proposals if total_proposals > 0 else None

        history = PredictiveUsageHistoryV1(
            entries=entries,
            total_proposals=total_proposals,
            total_accepted=total_accepted,
            total_rejected=total_rejected,
            total_expired=total_expired,
            total_pending=total_pending,
            acceptance_rate=acceptance_rate,
            avg_confidence_score=avg_confidence,
            revision=len(rows),
            latest_change_at=latest_change_at,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
        )

        return history

    def build_zone_patterns(
        self,
        zone_id: Optional[str] = None,
        since_revision: Optional[int] = None
    ) -> PredictiveZonePatternsV1:
        """Build zone predictive patterns read model."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM predictive_zone_patterns"
        params = []

        if zone_id:
            query += " WHERE zone_id = ?"
            params.append(zone_id)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        pattern_entries = []
        total_zones = 0
        zones_with_proposals = 0

        for row in rows:
            pattern = PredictiveZonePatternEntryV1(
                zone_id=row[1],
                zone_name=row[2],
                total_proposals=row[3],
                accepted_count=row[4],
                rejected_count=row[5],
                expired_count=row[6],
                acceptance_rate=row[7],
                avg_confidence_score=row[8],
                most_common_prediction_type=row[9] or "unknown",
                last_proposal_at=row[10],
                proposals_last_7_days=row[11],
                proposals_last_30_days=row[12],
                dominant_pattern_ids=eval(row[13]) if row[13] else [],
                revision=row[14] if len(row) > 14 else 0,
            )
            pattern_entries.append(pattern)
            total_zones += 1
            if row[3] > 0:
                zones_with_proposals += 1

        revision = sum(p.revision for p in pattern_entries) if pattern_entries else 0

        patterns = PredictiveZonePatternsV1(
            patterns=pattern_entries,
            total_zones=total_zones,
            zones_with_proposals=zones_with_proposals,
            revision=revision,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )
        return patterns

    def update_zone_pattern(self, pattern: PredictiveZonePatternEntryV1) -> None:
        """Update or insert zone pattern."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO predictive_zone_patterns 
            (zone_id, zone_name, total_proposals, accepted_count, rejected_count,
             expired_count, acceptance_rate, avg_confidence_score,
             most_common_prediction_type, last_proposal_at,
             proposals_last_7_days, proposals_last_30_days,
             dominant_pattern_ids, revision, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            pattern.zone_id, pattern.zone_name, pattern.total_proposals,
            pattern.accepted_count, pattern.rejected_count, pattern.expired_count,
            pattern.acceptance_rate, pattern.avg_confidence_score,
            pattern.most_common_prediction_type, pattern.last_proposal_at,
            pattern.proposals_last_7_days, pattern.proposals_last_30_days,
            str(pattern.dominant_pattern_ids), pattern.revision
        ))

        conn.commit()
        conn.close()

    def get_effectiveness_metrics(self) -> PredictiveEffectivenessMetricsV1:
        """Get effectiveness metrics read model."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM predictive_effectiveness_metrics WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        if not row:
            return PredictiveEffectivenessMetricsV1(
                total_proposals_analyzed=0,
                high_confidence_proposals=0,
                high_confidence_acceptance_rate=0.0,
                low_confidence_proposals=0,
                low_confidence_acceptance_rate=0.0,
                avg_time_to_accept_minutes=None,
                avg_time_to_reject_minutes=None,
                pattern_reinforcement_count=0,
                pattern_degradation_count=0,
                seasonal_adaptation_events=0,
                effectiveness_score=0.0,
                revision=0,
                latest_change_at=datetime.now(timezone.utc).isoformat(),
            )

        return PredictiveEffectivenessMetricsV1(
            total_proposals_analyzed=row[1] or 0,
            high_confidence_proposals=row[2] or 0,
            high_confidence_acceptance_rate=row[3] or 0.0,
            low_confidence_proposals=row[4] or 0,
            low_confidence_acceptance_rate=row[5] or 0.0,
            avg_time_to_accept_minutes=row[6],
            avg_time_to_reject_minutes=row[7],
            pattern_reinforcement_count=row[8] or 0,
            pattern_degradation_count=row[9] or 0,
            seasonal_adaptation_events=row[10] or 0,
            effectiveness_score=row[11] or 0.0,
            revision=row[12] or 0,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )

    def update_effectiveness_metrics(self, metrics: PredictiveEffectivenessMetricsV1) -> None:
        """Update effectiveness metrics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Increment revision
        new_revision = metrics.revision + 1

        cursor.execute("""
            UPDATE predictive_effectiveness_metrics SET
                total_proposals_analyzed = ?,
                high_confidence_proposals = ?,
                high_confidence_acceptance_rate = ?,
                low_confidence_proposals = ?,
                low_confidence_acceptance_rate = ?,
                avg_time_to_accept_minutes = ?,
                avg_time_to_reject_minutes = ?,
                pattern_reinforcement_count = ?,
                pattern_degradation_count = ?,
                seasonal_adaptation_events = ?,
                effectiveness_score = ?,
                revision = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        """, (
            metrics.total_proposals_analyzed, metrics.high_confidence_proposals,
            metrics.high_confidence_acceptance_rate, metrics.low_confidence_proposals,
            metrics.low_confidence_acceptance_rate, metrics.avg_time_to_accept_minutes,
            metrics.avg_time_to_reject_minutes, metrics.pattern_reinforcement_count,
            metrics.pattern_degradation_count, metrics.seasonal_adaptation_events,
            metrics.effectiveness_score, new_revision
        ))

        conn.commit()
        conn.close()

    def add_trend_entry(self, entry: PredictiveTrendEntryV1) -> None:
        """Add trend entry."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO predictive_trends 
            (period, timestamp, proposals_count, accepted_count, rejected_count,
             avg_confidence, acceptance_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.period, entry.timestamp, entry.proposals_count,
            entry.accepted_count, entry.rejected_count,
            entry.avg_confidence, entry.acceptance_rate
        ))

        conn.commit()
        conn.close()

    def build_trends(
        self,
        period: str = "daily",
        limit: int = 30
    ) -> PredictiveTrendsV1:
        """Build trends read model."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT period, timestamp, proposals_count, accepted_count,
                   rejected_count, avg_confidence, acceptance_rate
            FROM predictive_trends
            WHERE period = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (period, limit))
        rows = cursor.fetchall()
        conn.close()

        trend_entries = []
        for row in reversed(rows):  # Reverse to get chronological order
            entry = PredictiveTrendEntryV1(
                period=row[0],
                timestamp=row[1],
                proposals_count=row[2],
                accepted_count=row[3],
                rejected_count=row[4],
                avg_confidence=row[5],
                acceptance_rate=row[6],
            )
            trend_entries.append(entry)

        total_periods = len(trend_entries)
        trend_direction = "stable"
        trend_slope = 0.0

        # Calculate trend direction
        if total_periods >= 2:
            first_rate = trend_entries[0].acceptance_rate
            last_rate = trend_entries[-1].acceptance_rate
            trend_slope = last_rate - first_rate
            if trend_slope > 0.05:
                trend_direction = "improving"
            elif trend_slope < -0.05:
                trend_direction = "declining"

        trends = PredictiveTrendsV1(
            trends=trend_entries,
            period=period,
            total_periods=total_periods,
            trend_direction=trend_direction,
            trend_slope=trend_slope,
            revision=total_periods,
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )
        return trends

    def get_summary(self) -> PredictiveAnalyticsSummaryV1:
        """Get analytics summary."""
        usage = self.build_usage_history()
        patterns = self.build_zone_patterns()
        effectiveness = self.get_effectiveness_metrics()

        return PredictiveAnalyticsSummaryV1(
            usage=usage,
            patterns=patterns,
            effectiveness=effectiveness,
            summary_revision=max(usage.revision, patterns.revision, effectiveness.revision),
            latest_change_at=datetime.now(timezone.utc).isoformat(),
        )
