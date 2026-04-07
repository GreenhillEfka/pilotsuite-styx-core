"""Pydantic models for configuration validation.

Provides strict type validation, serialization, and migration support
for all configuration objects in the cross-module config system.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class BaseModelWithConfig(BaseModel):
    """Base model with common configuration."""
    
    model_config = ConfigDict(
        extra='forbid',  # Reject unknown fields
        validate_assignment=True,
        str_strip_whitespace=True,
    )


# ── Module-Specific Config Models ────────────────────────────────────


class SonosConfig(BaseModelWithConfig):
    """Sonos configuration for a zone."""
    
    room_name: str = Field(default="", max_length=100)
    favorite: str = Field(default="", max_length=500)
    uri: str = Field(default="", max_length=1000)
    volume_default: int = Field(default=30, ge=0, le=100)
    volume_ramp_start: int = Field(default=10, ge=0, le=100)
    volume_ramp_end: int = Field(default=40, ge=0, le=100)
    volume_ramp_minutes: int = Field(default=5, ge=1, le=120)
    follow_enabled: bool = True
    musikwolke_enabled: bool = False
    
    @field_validator('room_name')
    @classmethod
    def validate_room_name(cls, v: str) -> str:
        if v and not re.match(r'^[a-zA-Z0-9\s\-_]+$', v):
            raise ValueError('Room name contains invalid characters')
        return v
    
    @model_validator(mode='after')
    def validate_volume_ranges(self) -> SonosConfig:
        if self.volume_ramp_start > self.volume_ramp_end:
            raise ValueError('volume_ramp_start must be <= volume_ramp_end')
        if self.volume_default < self.volume_ramp_start or self.volume_default > self.volume_ramp_end:
            # Allow but warn - auto-adjust in application logic
            pass
        return self


class LightConfig(BaseModelWithConfig):
    """Light configuration for a zone."""
    
    entities: List[str] = Field(default_factory=list)
    brightness_default: int = Field(default=80, ge=0, le=255)
    color_temp_kelvin: int = Field(default=4000, ge=1000, le=20000)
    ramp_minutes: int = Field(default=10, ge=1, le=120)
    sunrise_enabled: bool = True
    sunset_enabled: bool = True
    
    @field_validator('entities')
    @classmethod
    def validate_entity_ids(cls, v: List[str]) -> List[str]:
        validated = []
        for entity in v:
            if not re.match(r'^[a-z_]+\.[a-z0-9_]+$', entity):
                raise ValueError(f'Invalid entity ID format: {entity}')
            validated.append(entity)
        return validated


class PresenceConfig(BaseModelWithConfig):
    """Presence tracking configuration for a zone."""
    
    motion_entities: List[str] = Field(default_factory=list)
    person_entities: List[str] = Field(default_factory=list)
    illuminance_entity: str = Field(default="", max_length=200)
    min_dwell_time_seconds: int = Field(default=600, ge=60, le=86400)
    auto_away_delay_seconds: int = Field(default=300, ge=60, le=86400)
    
    @field_validator('motion_entities', 'person_entities')
    @classmethod
    def validate_entity_lists(cls, v: List[str]) -> List[str]:
        for entity in v:
            if not re.match(r'^[a-z_]+\.[a-z0-9_]+$', entity):
                raise ValueError(f'Invalid entity ID format: {entity}')
        return v


class AlarmConfig(BaseModelWithConfig):
    """Alarm (Wecker) configuration for a zone."""
    
    enabled: bool = True
    default_time_hhmm: str = Field(default="07:00")
    repeat: str = Field(default="weekdays")  # once, daily, weekdays, weekends, custom
    custom_days: List[int] = Field(default_factory=list)  # 0=Mon..6=Sun
    snooze_minutes: int = Field(default=9, ge=1, le=60)
    auto_dismiss_minutes: int = Field(default=30, ge=1, le=120)
    
    @field_validator('default_time_hhmm')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        if not re.match(r'^([01]?\d|2[0-3]):[0-5]\d$', v):
            raise ValueError('Time must be in HH:MM format (24h)')
        return v
    
    @field_validator('repeat')
    @classmethod
    def validate_repeat(cls, v: str) -> str:
        valid = {'once', 'daily', 'weekdays', 'weekends', 'custom'}
        if v not in valid:
            raise ValueError(f'repeat must be one of: {valid}')
        return v
    
    @model_validator(mode='after')
    def validate_custom_days(self) -> AlarmConfig:
        if self.repeat == 'custom':
            if not self.custom_days:
                raise ValueError('custom_days required when repeat=custom')
            for day in self.custom_days:
                if not 0 <= day <= 6:
                    raise ValueError('custom_days must be 0-6 (Mon-Sun)')
        elif self.custom_days:
            # custom_days only relevant for custom repeat
            pass
        return self


class MoodConfig(BaseModelWithConfig):
    """Mood inference configuration for a zone."""
    
    enabled: bool = True
    media_entities: List[str] = Field(default_factory=list)
    min_dwell_time_seconds: int = Field(default=600, ge=60, le=86400)
    action_cooldown_seconds: int = Field(default=120, ge=10, le=3600)
    polling_interval_seconds: int = Field(default=300, ge=60, le=3600)
    character_weighting: bool = True
    
    @field_validator('media_entities')
    @classmethod
    def validate_media_entities(cls, v: List[str]) -> List[str]:
        for entity in v:
            if not re.match(r'^[a-z_]+\.[a-z0-9_]+$', entity):
                raise ValueError(f'Invalid entity ID format: {entity}')
        return v


# ── Zone Configuration ───────────────────────────────────────────────


class ZoneConfig(BaseModelWithConfig):
    """Unified zone configuration aggregating all module configs."""
    
    zone_id: str = Field(..., min_length=1, max_length=100)
    zone_name: str = Field(default="", max_length=200)
    area_id: str = Field(default="", max_length=100)
    
    # Module-specific configs
    sonos: SonosConfig = Field(default_factory=SonosConfig)
    light: LightConfig = Field(default_factory=LightConfig)
    presence: PresenceConfig = Field(default_factory=PresenceConfig)
    alarm: AlarmConfig = Field(default_factory=AlarmConfig)
    mood: MoodConfig = Field(default_factory=MoodConfig)
    
    # Metadata
    created_at: str = Field(default="")
    updated_at: str = Field(default="")
    
    # Smart defaults applied
    defaults_applied: bool = False
    
    @field_validator('zone_id')
    @classmethod
    def validate_zone_id(cls, v: str) -> str:
        if not re.match(r'^[a-z0-9_\-]+$', v):
            raise ValueError('zone_id must contain only lowercase letters, numbers, underscores, hyphens')
        return v
    
    @model_validator(mode='after')
    def set_timestamps(self) -> ZoneConfig:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        return self


# ── Conflict Detection ───────────────────────────────────────────────


class Conflict(BaseModelWithConfig):
    """A detected configuration conflict."""
    
    conflict_id: str = Field(..., min_length=1)
    severity: str  # "error", "warning", "info"
    modules: List[str]
    description: str
    resolution: str = ""
    affected_entities: List[str] = Field(default_factory=list)
    
    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v: str) -> str:
        valid = {'error', 'warning', 'info'}
        if v not in valid:
            raise ValueError(f'severity must be one of: {valid}')
        return v


# ── Config Version & Audit ───────────────────────────────────────────


class ConfigVersion(BaseModelWithConfig):
    """Version metadata for config snapshots."""
    
    version: int = Field(..., ge=1)
    created_at: str
    created_by: str = "system"
    commit_hash: str = Field(default="", max_length=40)
    description: str = Field(default="", max_length=500)
    zone_count: int
    checksum: str  # SHA256 of config content


class ConfigAuditEntry(BaseModelWithConfig):
    """Single audit log entry for config changes."""
    
    timestamp: str
    action: str  # create, update, delete, rollback, validate
    zone_id: Optional[str] = None
    field_path: Optional[str] = None  # e.g., "sonos.volume_default"
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    user: str = "system"
    reason: str = Field(default="", max_length=1000)
    success: bool = True
    error_message: Optional[str] = None


class ConfigAuditLog(BaseModelWithConfig):
    """Audit log container for config changes."""
    
    entries: List[ConfigAuditEntry] = Field(default_factory=list)
    max_entries: int = Field(default=1000, ge=100, le=10000)
    
    def add_entry(self, entry: ConfigAuditEntry) -> None:
        """Add entry with rotation."""
        self.entries.append(entry)
        # Rotate if exceeds max
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]


# ── Encrypted Fields Support ────────────────────────────────────────


class EncryptedField(BaseModelWithConfig):
    """Wrapper for encrypted sensitive field values.
    
    Usage: Store sensitive data (API keys, tokens, credentials) encrypted.
    The actual encryption/decryption is handled by the config manager.
    """
    
    algorithm: str = "fernet"  # fernet, aes-gcm
    ciphertext: str  # Base64-encoded encrypted data
    version: int = 1  # Key version for rotation support
    
    @property
    def is_encrypted(self) -> bool:
        return bool(self.ciphertext)
