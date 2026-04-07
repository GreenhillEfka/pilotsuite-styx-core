"""PilotSuite Database Layer — SQLAlchemy with Async Support."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Type
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.sql import func

logger = logging.getLogger(__name__)


# =============================================================================
# BASE MODEL
# =============================================================================

class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# =============================================================================
# MODELS
# =============================================================================

class Pattern(Base):
    """Learned pattern model."""
    __tablename__ = "patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)  # time, state, event
    trigger_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    actions: Mapped[Dict[str, Any]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_triggered: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_patterns_name", "name"),
        Index("ix_patterns_enabled", "enabled"),
    )


class Habit(Base):
    """Learned habit model."""
    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pattern_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("patterns.id"), nullable=True)
    frequency: Mapped[str] = mapped_column(String(50), default="daily")  # daily, weekly, monthly
    time_of_day: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    days_of_week: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)
    strength: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1 confidence
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_performed: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    performance_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_habits_user", "user_id"),
        Index("ix_habits_enabled", "enabled"),
    )


class VectorEntry(Base):
    """Vector store entry model."""
    __tablename__ = "vector_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(JSON, nullable=True)
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    collection: Mapped[str] = mapped_column(String(100), default="default", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class GraphNode(Base):
    """Knowledge graph node model."""
    __tablename__ = "graph_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    properties: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class GraphEdge(Base):
    """Knowledge graph edge model."""
    __tablename__ = "graph_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_node_id: Mapped[str] = mapped_column(String(255), ForeignKey("graph_nodes.node_id"), nullable=False, index=True)
    target_node_id: Mapped[str] = mapped_column(String(255), ForeignKey("graph_nodes.node_id"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    properties: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_edges_source_target", "source_node_id", "target_node_id"),
    )


class EnergyForecast(Base):
    """Energy forecast data model."""
    __tablename__ = "energy_forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # load, solar, price
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="kWh")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_forecasts_type_time", "forecast_type", "timestamp"),
    )


class AutomationLog(Base):
    """Automation execution log model."""
    __tablename__ = "automation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    automation_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    actions_executed: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class UserPreference(Base):
    """User preference model."""
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_preferences_user_category", "user_id", "category"),
    )


class Notification(Base):
    """Notification model."""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # -2 to 2
    channel: Mapped[str] = mapped_column(String(50), nullable=False)  # pushover, telegram, etc.
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    url_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    extra_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class CalendarEvent(Base):
    """Calendar event cache model."""
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    calendar_source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # google, caldav, etc.
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    attendees: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WeatherAutomationRule(Base):
    """Weather automation rule model."""
    __tablename__ = "weather_automation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    trigger_conditions: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    actions: Mapped[Dict[str, Any]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=0)
    last_triggered: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# =============================================================================
# DATABASE MANAGER
# =============================================================================

class DatabaseManager:
    """
    Database Manager — Async SQLAlchemy
    
    Features:
    - Async session management
    - Connection pooling
    - Automatic migrations (via Alembic)
    - CRUD operations
    """

    def __init__(self, database_url: str = "sqlite+aiosqlite:///./pilotsuite.db"):
        self.database_url = database_url
        self.engine = None
        self.async_session_maker = None

    async def init(self):
        """Initialize database connection."""
        # Create parent directories if needed
        if "sqlite" in self.database_url:
            db_path = Path(self.database_url.replace("sqlite+aiosqlite:///", ""))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.engine = create_async_engine(
            self.database_url,
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info(f"Database initialized: {self.database_url}")

    async def close(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
        logger.info("Database connection closed")

    async def get_session(self) -> AsyncSession:
        """Get database session."""
        async with self.async_session_maker() as session:
            yield session

    async def execute_query(self, query):
        """Execute a query and return results."""
        async with self.async_session_maker() as session:
            result = await session.execute(query)
            return result.all()

    async def add(self, model: Base) -> Base:
        """Add a model instance."""
        async with self.async_session_maker() as session:
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model

    async def update(self, model: Base, **kwargs) -> Base:
        """Update a model instance."""
        async with self.async_session_maker() as session:
            for key, value in kwargs.items():
                setattr(model, key, value)
            await session.commit()
            await session.refresh(model)
            return model

    async def delete(self, model: Base):
        """Delete a model instance."""
        async with self.async_session_maker() as session:
            await session.delete(model)
            await session.commit()


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if not _db_manager:
        _db_manager = DatabaseManager()
    return _db_manager


async def init_database(database_url: str = "sqlite+aiosqlite:///./pilotsuite.db"):
    """Initialize database."""
    db_manager = get_database_manager()
    db_manager.database_url = database_url
    await db_manager.init()
    return db_manager
