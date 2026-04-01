"""Configuration Engine — Slice 42.

Configuration management for PilotSuite Core.

Features:
- Hierarchical configuration
- Environment variable overrides
- Configuration validation
- Hot reloading
- Configuration versioning
- Schema-based validation
"""
from __future__ import annotations

import logging
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ConfigType(Enum):
    """Configuration value type."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class ConfigSource(Enum):
    """Configuration source."""
    DEFAULT = "default"
    FILE = "file"
    ENVIRONMENT = "environment"
    REMOTE = "remote"
    OVERRIDE = "override"


@dataclass
class ConfigSchema:
    """Schema for configuration validation."""
    key: str
    config_type: ConfigType
    required: bool = False
    default: Any = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None  # Regex pattern for strings
    enum_values: Optional[List[Any]] = None
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "type": self.config_type.value,
            "required": self.required,
            "default": self.default,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "pattern": self.pattern,
            "enum_values": self.enum_values,
            "description": self.description,
        }


@dataclass
class ConfigEntry:
    """Configuration entry."""
    key: str
    value: Any
    config_type: ConfigType
    source: ConfigSource
    schema: Optional[ConfigSchema] = None
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_by: str = "system"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "type": self.config_type.value,
            "source": self.source.value,
            "updated_at": self.updated_at,
            "updated_by": self.updated_by,
        }


@dataclass
class ConfigChange:
    """Configuration change record."""
    change_id: str
    key: str
    old_value: Any
    new_value: Any
    changed_by: str
    changed_at: str
    reason: str = ""
    source: ConfigSource = ConfigSource.OVERRIDE
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "key": self.key,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changed_by": self.changed_by,
            "changed_at": self.changed_at,
            "reason": self.reason,
            "source": self.source.value,
        }


class ConfigurationEngine:
    """Configuration management engine."""
    
    def __init__(self):
        self._configs: Dict[str, ConfigEntry] = {}
        self._schemas: Dict[str, ConfigSchema] = {}
        self._change_log: List[ConfigChange] = []
        self._max_log_size = 1000
        self._validation_errors: Dict[str, str] = {}
        
        # Callbacks for config changes
        self._change_callbacks: Dict[str, List[Callable]] = {}
        
        # Configuration groups/namespaces
        self._groups: Dict[str, List[str]] = {}  # group -> [keys]
        
        # Statistics
        self._stats = {
            "total_configs": 0,
            "total_changes": 0,
            "by_source": {},
        }
    
    def register_schema(self, key: str, config_type: str,
                       required: bool = False,
                       default: Any = None,
                       min_value: Optional[Union[int, float]] = None,
                       max_value: Optional[Union[int, float]] = None,
                       pattern: Optional[str] = None,
                       enum_values: Optional[List[Any]] = None,
                       description: str = "") -> None:
        """Register configuration schema."""
        schema = ConfigSchema(
            key=key,
            config_type=ConfigType(config_type),
            required=required,
            default=default,
            min_value=min_value,
            max_value=max_value,
            pattern=pattern,
            enum_values=enum_values,
            description=description,
        )
        
        self._schemas[key] = schema
        
        # Set default value if provided
        if default is not None:
            self._set_config(key, default, ConfigSource.DEFAULT, "system", "Default value")
        
        logger.debug("Schema registered: %s", key)
    
    def set_config(self, key: str, value: Any,
                  updated_by: str = "system",
                  reason: str = "") -> bool:
        """Set configuration value."""
        return self._set_config(key, value, ConfigSource.OVERRIDE, updated_by, reason)
    
    def _set_config(self, key: str, value: Any,
                   source: ConfigSource,
                   updated_by: str,
                   reason: str = "") -> bool:
        """Internal method to set configuration."""
        # Validate against schema
        if key in self._schemas:
            if not self._validate_value(key, value):
                self._validation_errors[key] = f"Config validation failed: {key}"
                logger.error("Config validation failed for %s", key)
                return False
            self._validation_errors.pop(key, None)
        
        # Determine config type
        config_type = self._infer_type(value)
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Check if key exists
        old_value = None
        if key in self._configs:
            old_value = self._configs[key].value
        
        # Create or update entry
        entry = ConfigEntry(
            key=key,
            value=value,
            config_type=config_type,
            source=source,
            schema=self._schemas.get(key),
            updated_at=now,
            updated_by=updated_by,
        )
        
        self._configs[key] = entry
        
        # Log change
        if old_value is not None or source != ConfigSource.DEFAULT:
            self._log_change(key, old_value, value, updated_by, reason, source)
        
        # Update stats
        self._stats["total_configs"] = len(self._configs)
        source_str = source.value
        self._stats["by_source"][source_str] = self._stats["by_source"].get(source_str, 0) + 1
        
        # Notify callbacks
        self._notify_change(key, value)
        
        logger.info("Config set: %s = %s (%s)", key, value, source.value)
        
        return True
    
    def _infer_type(self, value: Any) -> ConfigType:
        """Infer config type from value."""
        if isinstance(value, bool):
            return ConfigType.BOOLEAN
        elif isinstance(value, (int, float)):
            return ConfigType.NUMBER
        elif isinstance(value, str):
            return ConfigType.STRING
        elif isinstance(value, list):
            return ConfigType.ARRAY
        elif isinstance(value, dict):
            return ConfigType.OBJECT
        else:
            return ConfigType.STRING
    
    def _validate_value(self, key: str, value: Any) -> bool:
        """Validate value against schema."""
        schema = self._schemas.get(key)
        if not schema:
            return True
        
        # Type check
        if schema.config_type == ConfigType.STRING and not isinstance(value, str):
            return False
        elif schema.config_type == ConfigType.NUMBER and not isinstance(value, (int, float)):
            return False
        elif schema.config_type == ConfigType.BOOLEAN and not isinstance(value, bool):
            return False
        elif schema.config_type == ConfigType.OBJECT and not isinstance(value, dict):
            return False
        elif schema.config_type == ConfigType.ARRAY and not isinstance(value, list):
            return False
        
        # Min/max check
        if schema.min_value is not None and isinstance(value, (int, float)):
            if value < schema.min_value:
                return False
        if schema.max_value is not None and isinstance(value, (int, float)):
            if value > schema.max_value:
                return False
        
        # Enum check
        if schema.enum_values is not None:
            if value not in schema.enum_values:
                return False
        
        # Pattern check
        if schema.pattern is not None and isinstance(value, str):
            import re
            if not re.match(schema.pattern, value):
                return False
        
        return True
    
    def _log_change(self, key: str, old_value: Any, new_value: Any,
                   changed_by: str, reason: str,
                   source: ConfigSource) -> None:
        """Log configuration change."""
        change = ConfigChange(
            change_id=f"cfg_{uuid.uuid4().hex[:8]}",
            key=key,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            changed_at=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            source=source,
        )
        
        self._change_log.append(change)
        self._stats["total_changes"] += 1
        
        # Trim log
        if len(self._change_log) > self._max_log_size:
            self._change_log = self._change_log[-self._max_log_size:]
    
    def _notify_change(self, key: str, value: Any) -> None:
        """Notify callbacks of config change."""
        # Notify key-specific callbacks
        if key in self._change_callbacks:
            for callback in self._change_callbacks[key]:
                try:
                    callback(key, value)
                except Exception as exc:
                    logger.exception("Config callback failed for %s: %s", key, exc)
        
        # Notify wildcard callbacks
        if "*" in self._change_callbacks:
            for callback in self._change_callbacks["*"]:
                try:
                    callback(key, value)
                except Exception as exc:
                    logger.exception("Config callback failed for %s: %s", key, exc)
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        if key not in self._configs:
            # Check schema for default
            if key in self._schemas and self._schemas[key].default is not None:
                return self._schemas[key].default
            return default
        
        return self._configs[key].value
    
    def get_config_entry(self, key: str) -> Optional[Dict[str, Any]]:
        """Get configuration entry with metadata."""
        if key not in self._configs:
            return None
        
        return self._configs[key].to_dict()
    
    def get_all_configs(self, group: Optional[str] = None) -> Dict[str, Any]:
        """Get all configuration values."""
        if group:
            if group not in self._groups:
                return {}
            keys = self._groups[group]
            return {k: self._configs[k].value for k in keys if k in self._configs}
        
        return {k: v.value for k, v in self._configs.items()}
    
    def delete_config(self, key: str, deleted_by: str = "system") -> bool:
        """Delete configuration key."""
        if key not in self._configs:
            return False
        
        old_value = self._configs[key].value
        
        self._log_change(key, old_value, None, deleted_by, "Config deleted", ConfigSource.OVERRIDE)
        
        del self._configs[key]
        self._validation_errors.pop(key, None)
        self._stats["total_configs"] = len(self._configs)
        
        logger.info("Config deleted: %s", key)
        
        return True
    
    def load_from_dict(self, data: Dict[str, Any],
                      source: ConfigSource = ConfigSource.FILE,
                      loaded_by: str = "system") -> int:
        """Load configuration from dictionary."""
        count = 0
        
        for key, value in data.items():
            if self._set_config(key, value, source, loaded_by, "Loaded from dict"):
                count += 1
        
        logger.info("Loaded %d config values from dict", count)
        
        return count
    
    def load_from_env(self, prefix: str = "",
                     loaded_by: str = "system") -> int:
        """Load configuration from environment variables."""
        count = 0
        
        for key, value in os.environ.items():
            if prefix and not key.startswith(prefix):
                continue
            
            # Remove prefix
            config_key = key[len(prefix):] if prefix else key
            
            # Try to parse value
            parsed_value = self._parse_env_value(value)
            
            if self._set_config(config_key, parsed_value, ConfigSource.ENVIRONMENT, loaded_by, "Loaded from env"):
                count += 1
        
        logger.info("Loaded %d config values from environment", count)
        
        return count
    
    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value."""
        # Try boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
        
        # Try number
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # Try JSON
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
        
        # Return as string
        return value
    
    def load_from_file(self, filepath: str,
                      loaded_by: str = "system") -> int:
        """Load configuration from JSON file."""
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            
            return self.load_from_dict(data, ConfigSource.FILE, loaded_by)
        except Exception as exc:
            logger.error("Failed to load config from %s: %s", filepath, exc)
            return 0
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {k: v.value for k, v in self._configs.items()}
    
    def export_to_json(self, indent: int = 2) -> str:
        """Export configuration as JSON."""
        return json.dumps(self.export_to_dict(), indent=indent)
    
    def register_change_callback(self, key: str,
                                callback: Callable[[str, Any], None]) -> None:
        """Register callback for config changes."""
        if key not in self._change_callbacks:
            self._change_callbacks[key] = []
        
        self._change_callbacks[key].append(callback)
        
        logger.debug("Callback registered for config: %s", key)
    
    def add_to_group(self, group: str, keys: List[str]) -> None:
        """Add keys to configuration group."""
        if group not in self._groups:
            self._groups[group] = []
        
        for key in keys:
            if key not in self._groups[group]:
                self._groups[group].append(key)
    
    def get_group(self, group: str) -> Dict[str, Any]:
        """Get configuration group."""
        if group not in self._groups:
            return {}
        
        return {k: self._configs[k].value for k in self._groups[group] if k in self._configs}
    
    def get_change_log(self, key: Optional[str] = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        """Get configuration change log."""
        changes = self._change_log
        
        if key:
            changes = [c for c in changes if c.key == key]
        
        # Sort by changed_at (newest first)
        changes.sort(key=lambda c: c.changed_at, reverse=True)
        
        return [c.to_dict() for c in changes[:limit]]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get configuration statistics."""
        by_type = {}
        for entry in self._configs.values():
            ctype = entry.config_type.value
            by_type[ctype] = by_type.get(ctype, 0) + 1
        
        return {
            **self._stats,
            "by_type": by_type,
            "schemas_registered": len(self._schemas),
            "groups_defined": len(self._groups),
            "change_log_size": len(self._change_log),
        }
    
    def validate_all(self) -> Dict[str, Any]:
        """Validate all configuration values."""
        errors = list(self._validation_errors.values())
        warnings = []
        
        # Check required schemas
        for key, schema in self._schemas.items():
            if schema.required and key not in self._configs:
                errors.append(f"Required config missing: {key}")
            elif key in self._configs:
                if not self._validate_value(key, self._configs[key].value):
                    errors.append(f"Config validation failed: {key}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }
    
    def reset_to_defaults(self, reset_by: str = "system") -> int:
        """Reset all configs to schema defaults."""
        count = 0
        
        for key, schema in self._schemas.items():
            if schema.default is not None:
                if self._set_config(key, schema.default, ConfigSource.DEFAULT, reset_by, "Reset to default"):
                    count += 1
        
        logger.info("Reset %d configs to defaults", count)
        
        return count
    
    def clear_all(self, cleared_by: str = "system") -> int:
        """Clear all configuration values."""
        count = len(self._configs)
        
        for key in list(self._configs.keys()):
            self._log_change(key, self._configs[key].value, None, cleared_by, "Config cleared", ConfigSource.OVERRIDE)
            del self._configs[key]

        self._validation_errors.clear()

        self._stats["total_configs"] = 0
        
        logger.info("Cleared %d config values", count)
        
        return count


def create_configuration_engine() -> ConfigurationEngine:
    """Factory function to create configuration engine."""
    return ConfigurationEngine()
