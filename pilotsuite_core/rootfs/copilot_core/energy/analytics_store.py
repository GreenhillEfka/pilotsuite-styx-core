"""Energy Analytics Store — Slice 47."""
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from .analytics import (
    EnergyAnalyticsPeriod,
    EnergyAnalyticsSummaryV1,
    EnergyEffectivenessMetricsV1,
    EnergyUsageEntryV1,
    EnergyUsageHistoryV1,
    EnergyZonePatternsV1,
    ZoneEnergyPatternV1,
)


class EnergyAnalyticsStore:
    """Store for energy analytics read models."""
    
    def __init__(self, db_path: str = "/data/energy_analytics.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Usage history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS energy_usage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                zone_id TEXT NOT NULL,
                module_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                consumption_wh REAL NOT NULL,
                cost_eur REAL NOT NULL,
                tariff_rate TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Zone patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS zone_energy_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id TEXT UNIQUE NOT NULL,
                zone_name TEXT NOT NULL,
                avg_daily_consumption_wh REAL NOT NULL,
                peak_hour INTEGER NOT NULL,
                peak_consumption_wh REAL NOT NULL,
                off_peak_consumption_wh REAL NOT NULL,
                weekday_pattern TEXT,
                weekend_pattern TEXT,
                dominant_modules TEXT,
                trend_7d REAL DEFAULT 0.0,
                trend_30d REAL DEFAULT 0.0,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Effectiveness metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS effectiveness_metrics (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_savings_eur REAL DEFAULT 0.0,
                total_savings_wh REAL DEFAULT 0.0,
                optimization_success_rate REAL DEFAULT 0.0,
                avg_shift_duration_minutes REAL DEFAULT 0.0,
                peak_reduction_percentage REAL DEFAULT 0.0,
                pv_self_consumption_rate REAL DEFAULT 0.0,
                battery_efficiency REAL DEFAULT 0.0,
                suggestions_accepted INTEGER DEFAULT 0,
                suggestions_rejected INTEGER DEFAULT 0,
                suggestions_pending INTEGER DEFAULT 0,
                load_shifts_executed INTEGER DEFAULT 0,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Summary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics_summary (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                period TEXT NOT NULL,
                start_at TEXT NOT NULL,
                end_at TEXT NOT NULL,
                total_consumption_wh REAL DEFAULT 0.0,
                total_cost_eur REAL DEFAULT 0.0,
                avg_daily_consumption_wh REAL DEFAULT 0.0,
                peak_consumption_wh REAL DEFAULT 0.0,
                peak_hour INTEGER DEFAULT 0,
                zone_count INTEGER DEFAULT 0,
                module_count INTEGER DEFAULT 0,
                entity_count INTEGER DEFAULT 0,
                pv_generation_wh REAL DEFAULT 0.0,
                battery_cycles INTEGER DEFAULT 0,
                grid_import_wh REAL DEFAULT 0.0,
                grid_export_wh REAL DEFAULT 0.0,
                revision INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Initialize single-row metrics if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO effectiveness_metrics (id) VALUES (1)
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO analytics_summary (id, period, start_at, end_at) 
            VALUES (1, 'daily', ?, ?)
        """, (
            datetime.utcnow().isoformat() + "Z",
            (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z"
        ))
        
        conn.commit()
        conn.close()
    
    def add_usage_entry(self, entry: EnergyUsageEntryV1) -> None:
        """Add energy usage entry."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO energy_usage_history 
            (timestamp, zone_id, module_id, entity_id, consumption_wh, cost_eur, tariff_rate, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.timestamp, entry.zone_id, entry.module_id, entry.entity_id,
            entry.consumption_wh, entry.cost_eur, entry.tariff_rate, entry.source
        ))
        
        conn.commit()
        conn.close()
    
    def build_usage_history(
        self,
        period: EnergyAnalyticsPeriod,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        zone_id: Optional[str] = None,
        since_revision: Optional[int] = None
    ) -> EnergyUsageHistoryV1:
        """Build usage history read model."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate default time range
        now = datetime.utcnow()
        if period == EnergyAnalyticsPeriod.HOURLY:
            start = now - timedelta(hours=1)
        elif period == EnergyAnalyticsPeriod.DAILY:
            start = now - timedelta(days=1)
        elif period == EnergyAnalyticsPeriod.WEEKLY:
            start = now - timedelta(weeks=1)
        else:  # MONTHLY
            start = now - timedelta(days=30)
        
        # Use provided time range or default
        query_start = start_at or start.isoformat() + "Z"
        query_end = end_at or now.isoformat() + "Z"
        
        # Build query
        query = """
            SELECT timestamp, zone_id, module_id, entity_id, 
                   consumption_wh, cost_eur, tariff_rate, source
            FROM energy_usage_history
            WHERE timestamp >= ? AND timestamp <= ?
        """
        params = [query_start, query_end]
        
        if zone_id:
            query += " AND zone_id = ?"
            params.append(zone_id)
        
        if since_revision:
            query += " ORDER BY timestamp DESC LIMIT 100"
        else:
            query += " ORDER BY timestamp ASC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        # Build read model
        history = EnergyUsageHistoryV1(
            period=period,
            start_at=start_at,
            end_at=end_at,
        )
        
        for row in rows:
            entry = EnergyUsageEntryV1(
                timestamp=row[0],
                zone_id=row[1],
                module_id=row[2],
                entity_id=row[3],
                consumption_wh=row[4],
                cost_eur=row[5],
                tariff_rate=row[6],
                source=row[7],
            )
            history.add_entry(entry)
        
        return history
    
    def build_zone_patterns(
        self,
        zone_id: Optional[str] = None,
        since_revision: Optional[int] = None
    ) -> EnergyZonePatternsV1:
        """Build zone energy patterns read model."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM zone_energy_patterns"
        params = []
        
        if zone_id:
            query += " WHERE zone_id = ?"
            params.append(zone_id)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        patterns = EnergyZonePatternsV1()
        
        for row in rows:
            pattern = ZoneEnergyPatternV1(
                zone_id=row[1],
                zone_name=row[2],
                avg_daily_consumption_wh=row[3],
                peak_hour=row[4],
                peak_consumption_wh=row[5],
                off_peak_consumption_wh=row[6],
                weekday_pattern=eval(row[7]) if row[7] else [],
                weekend_pattern=eval(row[8]) if row[8] else [],
                dominant_modules=eval(row[9]) if row[9] else [],
                trend_7d=row[10] or 0.0,
                trend_30d=row[11] or 0.0,
            )
            patterns.add_pattern(pattern)
        
        return patterns
    
    def update_zone_pattern(self, pattern: ZoneEnergyPatternV1) -> None:
        """Update or insert zone pattern."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO zone_energy_patterns 
            (zone_id, zone_name, avg_daily_consumption_wh, peak_hour,
             peak_consumption_wh, off_peak_consumption_wh, weekday_pattern,
             weekend_pattern, dominant_modules, trend_7d, trend_30d, revision, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            pattern.zone_id, pattern.zone_name, pattern.avg_daily_consumption_wh,
            pattern.peak_hour, pattern.peak_consumption_wh, pattern.off_peak_consumption_wh,
            str(pattern.weekday_pattern), str(pattern.weekend_pattern),
            str(pattern.dominant_modules), pattern.trend_7d, pattern.trend_30d,
            pattern.revision
        ))
        
        conn.commit()
        conn.close()
    
    def get_effectiveness_metrics(self) -> EnergyEffectivenessMetricsV1:
        """Get effectiveness metrics read model."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM effectiveness_metrics WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return EnergyEffectivenessMetricsV1()
        
        return EnergyEffectivenessMetricsV1(
            total_savings_eur=row[1] or 0.0,
            total_savings_wh=row[2] or 0.0,
            optimization_success_rate=row[3] or 0.0,
            avg_shift_duration_minutes=row[4] or 0.0,
            peak_reduction_percentage=row[5] or 0.0,
            pv_self_consumption_rate=row[6] or 0.0,
            battery_efficiency=row[7] or 0.0,
            suggestions_accepted=row[8] or 0,
            suggestions_rejected=row[9] or 0,
            suggestions_pending=row[10] or 0,
            load_shifts_executed=row[11] or 0,
            revision=row[12] or 0,
        )
    
    def update_effectiveness_metrics(self, metrics: EnergyEffectivenessMetricsV1) -> None:
        """Update effectiveness metrics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Increment revision
        metrics.revision += 1
        
        cursor.execute("""
            UPDATE effectiveness_metrics SET
                total_savings_eur = ?,
                total_savings_wh = ?,
                optimization_success_rate = ?,
                avg_shift_duration_minutes = ?,
                peak_reduction_percentage = ?,
                pv_self_consumption_rate = ?,
                battery_efficiency = ?,
                suggestions_accepted = ?,
                suggestions_rejected = ?,
                suggestions_pending = ?,
                load_shifts_executed = ?,
                revision = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        """, (
            metrics.total_savings_eur, metrics.total_savings_wh,
            metrics.optimization_success_rate, metrics.avg_shift_duration_minutes,
            metrics.peak_reduction_percentage, metrics.pv_self_consumption_rate,
            metrics.battery_efficiency, metrics.suggestions_accepted,
            metrics.suggestions_rejected, metrics.suggestions_pending,
            metrics.load_shifts_executed, metrics.revision
        ))
        
        conn.commit()
        conn.close()
    
    def get_summary(self) -> EnergyAnalyticsSummaryV1:
        """Get analytics summary read model."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, period, start_at, end_at, total_consumption_wh, total_cost_eur,
                   avg_daily_consumption_wh, peak_consumption_wh, peak_hour,
                   zone_count, module_count, entity_count, pv_generation_wh,
                   battery_cycles, grid_import_wh, grid_export_wh, revision
            FROM analytics_summary WHERE id = 1
        """)
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return EnergyAnalyticsSummaryV1(
                period=EnergyAnalyticsPeriod.DAILY,
                start_at=datetime.utcnow().isoformat() + "Z",
                end_at=(datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
            )
        
        # Convert period string to enum
        try:
            period = EnergyAnalyticsPeriod(row[1])
        except (ValueError, TypeError):
            period = EnergyAnalyticsPeriod.DAILY
        
        return EnergyAnalyticsSummaryV1(
            period=period,
            start_at=row[2],
            end_at=row[3],
            total_consumption_wh=row[4] or 0.0,
            total_cost_eur=row[5] or 0.0,
            avg_daily_consumption_wh=row[6] or 0.0,
            peak_consumption_wh=row[7] or 0.0,
            peak_hour=row[8] or 0,
            zone_count=row[9] or 0,
            module_count=row[10] or 0,
            entity_count=row[11] or 0,
            pv_generation_wh=row[12] or 0.0,
            battery_cycles=row[13] or 0,
            grid_import_wh=row[14] or 0.0,
            grid_export_wh=row[15] or 0.0,
            revision=row[16] or 0,
        )
    
    def update_summary(self, summary: EnergyAnalyticsSummaryV1) -> None:
        """Update analytics summary."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Increment revision
        summary.revision += 1
        
        cursor.execute("""
            UPDATE analytics_summary SET
                period = ?,
                start_at = ?,
                end_at = ?,
                total_consumption_wh = ?,
                total_cost_eur = ?,
                avg_daily_consumption_wh = ?,
                peak_consumption_wh = ?,
                peak_hour = ?,
                zone_count = ?,
                module_count = ?,
                entity_count = ?,
                pv_generation_wh = ?,
                battery_cycles = ?,
                grid_import_wh = ?,
                grid_export_wh = ?,
                revision = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        """, (
            summary.period.value, summary.start_at, summary.end_at,
            summary.total_consumption_wh, summary.total_cost_eur,
            summary.avg_daily_consumption_wh, summary.peak_consumption_wh,
            summary.peak_hour, summary.zone_count, summary.module_count,
            summary.entity_count, summary.pv_generation_wh, summary.battery_cycles,
            summary.grid_import_wh, summary.grid_export_wh, summary.revision
        ))
        
        conn.commit()
        conn.close()
