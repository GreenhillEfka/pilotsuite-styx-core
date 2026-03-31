"""Config Hub — Slice 74.

Zentrale Konfiguration für alle Zone-aware Module.

Features:
- Zone-Specific Configuration
- Module Configuration Registry
- Configuration Inheritance (Global → Zone → Override)
- Configuration Validation
- Configuration History
- Configuration Export/Import
- Default Profiles
- Configuration Change Events
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Callable, Type
from enum import Enum
import uuid
import json

logger = logging.getLogger(__name__)


class ConfigScope(Enum):
    """Configuration scope levels."""
    GLOBAL = "global"  # System-wide defaults
    ZONE = "zone"  # Zone-specific overrides
    MODULE = "module"  # Module-specific settings
    RULE = "rule"  # Rule-specific settings


class ConfigType(Enum):
    """Configuration value types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    ENUM = "enum"


@dataclass
class ConfigField:
    """Configuration field definition."""
    name: str
    config_type: ConfigType
    description: str
    default: Any = None
    required: bool = False
    min_value: Optional[Any] = None  # For numeric types
    max_value: Optional[Any] = None  # For numeric types
    options: Optional[List[Any]] = None  # For enum types
    scope: ConfigScope = ConfigScope.MODULE
    zone_id: Optional[str] = None
    
    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate a value against this field."""
        if value is None:
            if self.required:
                return False, f"Field '{self.name}' is required"
            return True, None
        
        # Type validation
        if self.config_type == ConfigType.STRING:
            if not isinstance(value, str):
                return False, f"Field '{self.name}' must be a string"
        elif self.config_type == ConfigType.INTEGER:
            if not isinstance(value, int):
                return False, f"Field '{self.name}' must be an integer"
            if self.min_value is not None and value < self.min_value:
                return False, f"Field '{self.name}' must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Field '{self.name}' must be <= {self.max_value}"
        elif self.config_type == ConfigType.FLOAT:
            if not isinstance(value, (int, float)):
                return False, f"Field '{self.name}' must be a number"
            if self.min_value is not None and value < self.min_value:
                return False, f"Field '{self.name}' must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Field '{self.name}' must be <= {self.max_value}"
        elif self.config_type == ConfigType.BOOLEAN:
            if not isinstance(value, bool):
                return False, f"Field '{self.name}' must be a boolean"
        elif self.config_type == ConfigType.LIST:
            if not isinstance(value, list):
                return False, f"Field '{self.name}' must be a list"
        elif self.config_type == ConfigType.DICT:
            if not isinstance(value, dict):
                return False, f"Field '{self.name}' must be an object"
        elif self.config_type == ConfigType.ENUM:
            if self.options and value not in self.options:
                return False, f"Field '{self.name}' must be one of {self.options}"
        
        return True, None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.config_type.value,
            "description": self.description,
            "default": self.default,
            "required": self.required,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "options": self.options,
            "scope": self.scope.value,
            "zone_id": self.zone_id,
        }


@dataclass
class ModuleConfig:
    """Configuration for a module."""
    module_id: str
    module_name: str
    zone_id: Optional[str]  # None = global
    fields: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "module_name": self.module_name,
            "zone_id": self.zone_id,
            "fields": self.fields,
            "enabled": self.enabled,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class ConfigChange:
    """Configuration change record."""
    change_id: str
    module_id: str
    zone_id: Optional[str]
    field_name: str
    old_value: Any
    new_value: Any
    changed_by: str = "system"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "module_id": self.module_id,
            "zone_id": self.zone_id,
            "field_name": self.field_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changed_by": self.changed_by,
            "timestamp": self.timestamp,
            "reason": self.reason,
        }


@dataclass
class ZoneProfile:
    """Zone configuration profile."""
    profile_id: str
    name: str
    zone_id: str
    description: str = ""
    module_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    is_default: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "zone_id": self.zone_id,
            "description": self.description,
            "module_configs": self.module_configs,
            "is_default": self.is_default,
            "created_at": self.created_at,
        }


class ConfigHub:
    """Central configuration hub for all zone-aware modules.
    
    Architecture:
        Global Defaults → Zone Profiles → Module Overrides → Runtime Config
    
    Usage:
        hub = ConfigHub()
        hub.register_module_schema("presence", presence_fields)
        hub.set_zone_config("zone_living", "presence", {"off_delay": 300})
        config = hub.get_effective_config("zone_living", "presence")
    """
    
    def __init__(self):
        self._module_schemas: Dict[str, List[ConfigField]] = {}
        self._module_configs: Dict[str, ModuleConfig] = {}
        self._zone_profiles: Dict[str, ZoneProfile] = {}
        self._change_history: List[ConfigChange] = []
        self._global_defaults: Dict[str, Dict[str, Any]] = {}
        self._callbacks: List[Callable] = []
        
        # Initialize default global settings
        self._init_global_defaults()
        
        logger.info("ConfigHub initialized")
    
    def _init_global_defaults(self) -> None:
        """Initialize global default configurations."""
        self._global_defaults = {
            "presence": {
                "off_delay_seconds": 300,
                "on_delay_seconds": 0,
                "extended_absence_threshold_seconds": 43200,
                "require_multiple_sensors": False,
                "min_confidence_threshold": 0.5,
            },
            "light": {
                "brightness_threshold": 0.3,
                "auto_on_enabled": True,
                "auto_off_enabled": True,
                "auto_off_delay_seconds": 300,
                "default_brightness": 0.8,
                "default_color_temp": 4000,
            },
            "timeofday": {
                "night_start": 22,
                "morning_start": 6,
                "seasonal_adjustment_enabled": True,
                "weekend_mode_enabled": True,
            },
        }
    
    def register_module_schema(self, module_name: str,
                              fields: List[ConfigField]) -> bool:
        """Register configuration schema for a module."""
        with self._lock():
            self._module_schemas[module_name] = fields
        
        logger.info("Module schema registered: %s (%d fields)", module_name, len(fields))
        return True
    
    def get_module_schema(self, module_name: str) -> Optional[List[ConfigField]]:
        """Get configuration schema for a module."""
        return self._module_schemas.get(module_name)
    
    def set_zone_config(self, zone_id: str, module_name: str,
                       fields: Dict[str, Any],
                       changed_by: str = "system") -> bool:
        """Set zone-specific configuration for a module."""
        config_id = f"{module_name}_{zone_id}"
        
        # Validate fields against schema
        schema = self._module_schemas.get(module_name, [])
        validation_errors = []
        
        for field_def in schema:
            if field_def.name in fields:
                valid, error = field_def.validate(fields[field_def.name])
                if not valid:
                    validation_errors.append(error)
        
        if validation_errors:
            logger.error("Config validation failed: %s", validation_errors)
            return False
        
        # Get or create config
        if config_id in self._module_configs:
            old_config = self._module_configs[config_id]
            old_fields = old_config.fields.copy()
        else:
            old_config = None
            old_fields = {}
        
        # Record changes
        for field_name, new_value in fields.items():
            old_value = old_fields.get(field_name)
            
            if old_value != new_value:
                change = ConfigChange(
                    change_id=f"cfg_{uuid.uuid4().hex[:16]}",
                    module_id=module_name,
                    zone_id=zone_id,
                    field_name=field_name,
                    old_value=old_value,
                    new_value=new_value,
                    changed_by=changed_by,
                )
                self._change_history.append(change)
        
        # Create/update config
        now = datetime.now(timezone.utc).isoformat()
        
        if old_config:
            old_config.fields.update(fields)
            old_config.updated_at = now
        else:
            config = ModuleConfig(
                module_id=config_id,
                module_name=module_name,
                zone_id=zone_id,
                fields=fields,
            )
            self._module_configs[config_id] = config
        
        # Notify callbacks
        self._notify_callbacks(module_name, zone_id, fields)
        
        # Limit change history (last 1000)
        if len(self._change_history) > 1000:
            self._change_history = self._change_history[-1000:]
        
        logger.info("Zone config set: %s/%s (%d fields)", zone_id, module_name, len(fields))
        return True
    
    def get_zone_config(self, zone_id: str, module_name: str) -> Optional[ModuleConfig]:
        """Get zone-specific configuration for a module."""
        config_id = f"{module_name}_{zone_id}"
        return self._module_configs.get(config_id)
    
    def get_effective_config(self, zone_id: str, module_name: str) -> Dict[str, Any]:
        """Get effective configuration (global + zone + overrides merged)."""
        # Start with global defaults
        config = self._global_defaults.get(module_name, {}).copy()
        
        # Apply zone profile if exists
        if zone_id in self._zone_profiles:
            profile = self._zone_profiles[zone_id]
            if module_name in profile.module_configs:
                config.update(profile.module_configs[module_name])
        
        # Apply zone-specific config
        zone_config = self.get_zone_config(zone_id, module_name)
        if zone_config:
            config.update(zone_config.fields)
        
        return config
    
    def get_global_defaults(self, module_name: str) -> Dict[str, Any]:
        """Get global defaults for a module."""
        return self._global_defaults.get(module_name, {}).copy()
    
    def set_global_default(self, module_name: str,
                          field_name: str, value: Any) -> bool:
        """Set global default for a module field."""
        if module_name not in self._global_defaults:
            self._global_defaults[module_name] = {}
        
        self._global_defaults[module_name][field_name] = value
        
        logger.info("Global default set: %s/%s = %s", module_name, field_name, value)
        return True
    
    def create_zone_profile(self, profile: ZoneProfile) -> str:
        """Create a zone configuration profile."""
        with self._lock():
            self._zone_profiles[profile.zone_id] = profile
        
        logger.info("Zone profile created: %s (%s)", profile.profile_id, profile.name)
        return profile.profile_id
    
    def get_zone_profile(self, zone_id: str) -> Optional[ZoneProfile]:
        """Get zone configuration profile."""
        return self._zone_profiles.get(zone_id)
    
    def delete_zone_profile(self, zone_id: str) -> bool:
        """Delete a zone configuration profile."""
        if zone_id not in self._zone_profiles:
            return False
        
        with self._lock():
            del self._zone_profiles[zone_id]
        
        return True
    
    def get_change_history(self, module_name: Optional[str] = None,
                          zone_id: Optional[str] = None,
                          limit: int = 100) -> List[ConfigChange]:
        """Get configuration change history."""
        changes = self._change_history
        
        if module_name:
            changes = [c for c in changes if c.module_id == module_name]
        
        if zone_id:
            changes = [c for c in changes if c.zone_id == zone_id]
        
        return changes[-limit:]
    
    def register_callback(self, callback: Callable) -> None:
        """Register callback for configuration changes."""
        self._callbacks.append(callback)
    
    def _notify_callbacks(self, module_name: str, zone_id: str,
                         fields: Dict[str, Any]) -> None:
        """Notify registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(module_name, zone_id, fields)
            except Exception as e:
                logger.exception("Config callback failed: %s", e)
    
    def export_config(self, zone_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        export = {
            "global_defaults": self._global_defaults,
            "zone_profiles": {},
            "module_configs": {},
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Export zone profiles
        for zone_id, profile in self._zone_profiles.items():
            if zone_ids is None or zone_id in zone_ids:
                export["zone_profiles"][zone_id] = profile.to_dict()
        
        # Export module configs
        for config_id, config in self._module_configs.items():
            if zone_ids is None or config.zone_id in zone_ids:
                export["module_configs"][config_id] = config.to_dict()
        
        return export
    
    def import_config(self, config_data: Dict[str, Any],
                     merge: bool = True) -> bool:
        """Import configuration from dictionary."""
        try:
            # Import global defaults
            if "global_defaults" in config_data:
                if merge:
                    for module_name, defaults in config_data["global_defaults"].items():
                        if module_name not in self._global_defaults:
                            self._global_defaults[module_name] = {}
                        self._global_defaults[module_name].update(defaults)
                else:
                    self._global_defaults = config_data["global_defaults"]
            
            # Import zone profiles
            if "zone_profiles" in config_data:
                for zone_id, profile_data in config_data["zone_profiles"].items():
                    profile = ZoneProfile(
                        profile_id=profile_data["profile_id"],
                        name=profile_data["name"],
                        zone_id=profile_data["zone_id"],
                        description=profile_data.get("description", ""),
                        module_configs=profile_data.get("module_configs", {}),
                        is_default=profile_data.get("is_default", False),
                    )
                    self._zone_profiles[zone_id] = profile
            
            # Import module configs
            if "module_configs" in config_data:
                for config_id, config_data_item in config_data["module_configs"].items():
                    config = ModuleConfig(
                        module_id=config_data_item["module_id"],
                        module_name=config_data_item["module_name"],
                        zone_id=config_data_item["zone_id"],
                        fields=config_data_item.get("fields", {}),
                        enabled=config_data_item.get("enabled", True),
                        version=config_data_item.get("version", "1.0.0"),
                    )
                    self._module_configs[config_id] = config
            
            logger.info("Configuration imported successfully")
            return True
            
        except Exception as e:
            logger.exception("Config import failed: %s", e)
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get configuration hub statistics."""
        zone_configs = {}
        for config in self._module_configs.values():
            if config.zone_id:
                zone_configs[config.zone_id] = zone_configs.get(config.zone_id, 0) + 1
        
        return {
            "registered_schemas": len(self._module_schemas),
            "total_configs": len(self._module_configs),
            "zone_profiles": len(self._zone_profiles),
            "zones_with_config": len(zone_configs),
            "total_change_history": len(self._change_history),
            "registered_callbacks": len(self._callbacks),
            "global_defaults_modules": len(self._global_defaults),
        }
    
    def validate_config(self, module_name: str,
                       fields: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate configuration fields against schema."""
        schema = self._module_schemas.get(module_name, [])
        errors = []
        
        # Check required fields
        for field_def in schema:
            if field_def.required and field_def.name not in fields:
                errors.append(f"Required field missing: {field_def.name}")
        
        # Validate each field
        for field_def in schema:
            if field_def.name in fields:
                valid, error = field_def.validate(fields[field_def.name])
                if not valid:
                    errors.append(error)
        
        return len(errors) == 0, errors
    
    def get_all_zone_configs(self, module_name: str) -> Dict[str, ModuleConfig]:
        """Get all zone configs for a module."""
        result = {}
        
        for config_id, config in self._module_configs.items():
            if config.module_name == module_name and config.zone_id:
                result[config.zone_id] = config
        
        return result
    
    def _lock(self):
        """Simple context manager for thread safety."""
        import threading
        return threading.Lock()


def create_config_hub() -> ConfigHub:
    """Factory function to create config hub."""
    return ConfigHub()


# Pre-built schema templates
def get_presence_config_schema() -> List[ConfigField]:
    """Get configuration schema for presence module."""
    return [
        ConfigField(
            name="off_delay_seconds",
            config_type=ConfigType.INTEGER,
            description="Delay before marking zone as absent",
            default=300,
            min_value=0,
            max_value=3600,
        ),
        ConfigField(
            name="on_delay_seconds",
            config_type=ConfigType.INTEGER,
            description="Delay before marking zone as present",
            default=0,
            min_value=0,
            max_value=300,
        ),
        ConfigField(
            name="extended_absence_threshold_seconds",
            config_type=ConfigType.INTEGER,
            description="Time before marking as extended absent",
            default=43200,
            min_value=3600,
            max_value=604800,
        ),
        ConfigField(
            name="require_multiple_sensors",
            config_type=ConfigType.BOOLEAN,
            description="Require multiple sensors for presence detection",
            default=False,
        ),
        ConfigField(
            name="min_confidence_threshold",
            config_type=ConfigType.FLOAT,
            description="Minimum confidence for presence detection",
            default=0.5,
            min_value=0.0,
            max_value=1.0,
        ),
    ]


def get_light_config_schema() -> List[ConfigField]:
    """Get configuration schema for light module."""
    return [
        ConfigField(
            name="brightness_threshold",
            config_type=ConfigType.FLOAT,
            description="Light level threshold for auto-on",
            default=0.3,
            min_value=0.0,
            max_value=1.0,
        ),
        ConfigField(
            name="auto_on_enabled",
            config_type=ConfigType.BOOLEAN,
            description="Enable automatic light on",
            default=True,
        ),
        ConfigField(
            name="auto_off_enabled",
            config_type=ConfigType.BOOLEAN,
            description="Enable automatic light off",
            default=True,
        ),
        ConfigField(
            name="auto_off_delay_seconds",
            config_type=ConfigType.INTEGER,
            description="Delay before auto-off",
            default=300,
            min_value=0,
            max_value=3600,
        ),
        ConfigField(
            name="default_brightness",
            config_type=ConfigType.FLOAT,
            description="Default brightness level",
            default=0.8,
            min_value=0.0,
            max_value=1.0,
        ),
        ConfigField(
            name="default_color_temp",
            config_type=ConfigType.INTEGER,
            description="Default color temperature in Kelvin",
            default=4000,
            min_value=2000,
            max_value=6500,
        ),
    ]


def get_timeofday_config_schema() -> List[ConfigField]:
    """Get configuration schema for time of day module."""
    return [
        ConfigField(
            name="night_start",
            config_type=ConfigType.INTEGER,
            description="Night phase start hour",
            default=22,
            min_value=0,
            max_value=23,
        ),
        ConfigField(
            name="morning_start",
            config_type=ConfigType.INTEGER,
            description="Morning phase start hour",
            default=6,
            min_value=0,
            max_value=23,
        ),
        ConfigField(
            name="seasonal_adjustment_enabled",
            config_type=ConfigType.BOOLEAN,
            description="Enable seasonal adjustments",
            default=True,
        ),
        ConfigField(
            name="weekend_mode_enabled",
            config_type=ConfigType.BOOLEAN,
            description="Enable weekend mode",
            default=True,
        ),
    ]
