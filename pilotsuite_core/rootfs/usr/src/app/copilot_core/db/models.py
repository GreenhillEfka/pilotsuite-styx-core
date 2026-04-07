"""Database Models (SQLite ORM).

Core models for persistent data in PilotSuite v1.0.0.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone

Base = declarative_base()

class ZoneModel(Base):
    __tablename__ = 'zones'
    id = Column(Integer, primary_key=True)
    zone_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100))
    zone_type = Column(String(50))
    config_json = Column(Text) # JSON blob
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class UserModel(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), unique=True, nullable=False)
    preferences_json = Column(Text)
    last_active = Column(DateTime)

class TaskModel(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    task_id = Column(String(100), unique=True)
    name = Column(String(200))
    status = Column(String(20)) # pending, running, completed, failed
    payload = Column(Text) # JSON
    result = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime)
