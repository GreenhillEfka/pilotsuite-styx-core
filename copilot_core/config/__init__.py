"""Central configuration layer for Copilot Core.

Provides unified configuration management across modules:
- cross_module: Cross-module zone configuration and conflict detection
- models: Pydantic models for validation
- manager: Config manager with encryption, versioning, audit logging
- encryption: Encryption utilities for sensitive data
"""
from .cross_module import (
    CrossModuleConfig,
    ZoneConfig as CrossModuleZoneConfig,
    SonosConfig as CrossModuleSonosConfig,
    LightConfig as CrossModuleLightConfig,
    PresenceConfig as CrossModulePresenceConfig,
    AlarmConfig as CrossModuleAlarmConfig,
    MoodConfig as CrossModuleMoodConfig,
    Conflict as CrossModuleConflict,
    async_get_cross_module_config,
)
from .models import (
    ZoneConfig,
    SonosConfig,
    LightConfig,
    PresenceConfig,
    AlarmConfig,
    MoodConfig,
    Conflict,
    ConfigVersion,
    ConfigAuditEntry,
    ConfigAuditLog,
    EncryptedField,
)
from .manager import (
    ConfigManager,
    ConfigValidationError,
    ConfigRollbackError,
    async_get_config_manager,
)
from .encryption import (
    ConfigEncryption,
    SecretManager,
    EncryptionError,
    encrypt_value,
    decrypt_value,
)

__all__ = [
    # Cross-module (legacy)
    "CrossModuleConfig",
    "CrossModuleZoneConfig",
    "CrossModuleSonosConfig",
    "CrossModuleLightConfig",
    "CrossModulePresenceConfig",
    "CrossModuleAlarmConfig",
    "CrossModuleMoodConfig",
    "CrossModuleConflict",
    "async_get_cross_module_config",
    
    # Pydantic models
    "ZoneConfig",
    "SonosConfig",
    "LightConfig",
    "PresenceConfig",
    "AlarmConfig",
    "MoodConfig",
    "Conflict",
    "ConfigVersion",
    "ConfigAuditEntry",
    "ConfigAuditLog",
    "EncryptedField",
    
    # Manager
    "ConfigManager",
    "ConfigValidationError",
    "ConfigRollbackError",
    "async_get_config_manager",
    
    # Encryption
    "ConfigEncryption",
    "SecretManager",
    "EncryptionError",
    "encrypt_value",
    "decrypt_value",
]
