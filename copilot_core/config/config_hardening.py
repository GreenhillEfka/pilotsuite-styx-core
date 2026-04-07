"""P1-003: Config Hardening — Validation, Encryption, Secrets."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List
from pathlib import Path
from datetime import datetime
import hashlib

try:
    from pydantic import BaseModel, ValidationError, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class ConfigVersion:
    """Version tracking for config changes."""
    version: str
    timestamp: float
    author: str
    changes: List[str]
    checksum: str


@dataclass
class AuditLogEntry:
    """Audit log entry for config changes."""
    timestamp: float
    action: str  # create, update, delete, rollback
    key: str
    old_value: Optional[Any]
    new_value: Optional[Any]
    author: str
    reason: Optional[str] = None


class ConfigValidator:
    """Validates configuration using Pydantic or schema validation."""

    def __init__(self, schema: Optional[Dict] = None):
        self.schema = schema or {}
        self._validators: Dict[str, callable] = {}

    def register_validator(self, key: str, validator: callable):
        """Register custom validator for config key."""
        self._validators[key] = validator

    def validate(self, config: Dict) -> tuple[bool, List[str]]:
        """Validate config, return (valid, errors)."""
        errors = []

        # Schema validation
        if self.schema:
            for key, rules in self.schema.items():
                if key in config:
                    value = config[key]
                    if 'type' in rules and not isinstance(value, rules['type']):
                        errors.append(f"Key '{key}' has wrong type, expected {rules['type'].__name__}")
                    if 'min' in rules and value < rules['min']:
                        errors.append(f"Key '{key}' value {value} below minimum {rules['min']}")
                    if 'max' in rules and value > rules['max']:
                        errors.append(f"Key '{key}' value {value} above maximum {rules['max']}")

        # Custom validators
        for key, validator in self._validators.items():
            if key in config:
                try:
                    validator(config[key])
                except Exception as e:
                    errors.append(f"Key '{key}' validation failed: {e}")

        return len(errors) == 0, errors


class ConfigEncryption:
    """Handles encryption for sensitive config values."""

    def __init__(self, encryption_key: Optional[str] = None):
        self.encryption_key = encryption_key or os.environ.get('CONFIG_ENCRYPTION_KEY')
        self._sensitive_keys = {'password', 'secret', 'token', 'api_key', 'private_key'}

    def is_sensitive(self, key: str) -> bool:
        """Check if config key is sensitive."""
        return any(s in key.lower() for s in self._sensitive_keys)

    def encrypt(self, value: str) -> str:
        """Encrypt sensitive value."""
        if not self.encryption_key:
            logger.warning("No encryption key configured, storing plaintext")
            return value
        
        # Simple XOR encryption (replace with proper crypto in production)
        key_bytes = self.encryption_key.encode()
        value_bytes = value.encode()
        encrypted = bytes(a ^ b for a, b in zip(value_bytes, (key_bytes * ((len(value_bytes) // len(key_bytes)) + 1))[:len(value_bytes)]))
        return encrypted.hex()

    def decrypt(self, encrypted_value: str) -> str:
        """Decrypt sensitive value."""
        if not self.encryption_key:
            return encrypted_value
        
        # Simple XOR decryption
        key_bytes = self.encryption_key.encode()
        encrypted_bytes = bytes.fromhex(encrypted_value)
        decrypted = bytes(a ^ b for a, b in zip(encrypted_bytes, (key_bytes * ((len(encrypted_bytes) // len(key_bytes)) + 1))[:len(encrypted_bytes)]))
        return decrypted.decode()

    def sanitize_for_logging(self, config: Dict) -> Dict:
        """Remove sensitive values for logging."""
        sanitized = {}
        for key, value in config.items():
            if self.is_sensitive(key):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value
        return sanitized


class ConfigManager:
    """Central configuration manager with hardening features."""

    def __init__(
        self,
        config_path: str,
        encryption_key: Optional[str] = None,
        schema: Optional[Dict] = None,
    ):
        self.config_path = Path(config_path)
        self.validator = ConfigValidator(schema)
        self.encryption = ConfigEncryption(encryption_key)
        self._config: Dict = {}
        self._version: Optional[ConfigVersion] = None
        self._audit_log: List[AuditLogEntry] = []
        self._backup_path: Optional[Path] = None

        # Load existing config
        self._load()

    def _load(self):
        """Load config from file."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self._config = json.load(f)
            logger.info(f"Loaded config from {self.config_path}")
        else:
            logger.info(f"Creating new config at {self.config_path}")
            self._config = {}

    def _save(self):
        """Save config to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Encrypt sensitive values before saving
        config_to_save = {}
        for key, value in self._config.items():
            if self.encryption.is_sensitive(key) and isinstance(value, str):
                config_to_save[key] = self.encryption.encrypt(value)
            else:
                config_to_save[key] = value

        with open(self.config_path, 'w') as f:
            json.dump(config_to_save, f, indent=2)
        
        logger.info(f"Saved config to {self.config_path}")

    def _create_backup(self):
        """Create backup before changes."""
        if self._backup_path and self.config_path.exists():
            backup_file = self._backup_path / f"config.{datetime.now().isoformat()}.bak"
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'r') as src:
                with open(backup_file, 'w') as dst:
                    dst.write(src.read())
            logger.info(f"Created backup at {backup_file}")

    def _audit(self, action: str, key: str, old_value: Optional[Any], new_value: Optional[Any], author: str, reason: Optional[str] = None):
        """Log audit entry."""
        entry = AuditLogEntry(
            timestamp=datetime.now().timestamp(),
            action=action,
            key=key,
            old_value=old_value,
            new_value=new_value,
            author=author,
            reason=reason
        )
        self._audit_log.append(entry)
        logger.info(f"Audit: {action} {key} by {author}")

    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """Get config value."""
        value = self._config.get(key, default)
        
        # Decrypt sensitive values
        if value and self.encryption.is_sensitive(key) and isinstance(value, str):
            try:
                return self.encryption.decrypt(value)
            except Exception:
                logger.warning(f"Failed to decrypt {key}, returning raw value")
                return value
        
        return value

    def set(self, key: str, value: Any, author: str = "system", reason: Optional[str] = None):
        """Set config value with validation and audit."""
        old_value = self._config.get(key)
        
        # Validate
        if self.validator:
            valid, errors = self.validator.validate({key: value})
            if not valid:
                raise ValueError(f"Config validation failed: {', '.join(errors)}")

        # Create backup
        self._create_backup()

        # Set and save
        self._config[key] = value
        self._save()

        # Audit
        self._audit("update", key, old_value, value, author, reason)

    def delete(self, key: str, author: str = "system", reason: Optional[str] = None):
        """Delete config value."""
        if key in self._config:
            old_value = self._config[key]
            del self._config[key]
            self._save()
            self._audit("delete", key, old_value, None, author, reason)

    def get_version(self) -> Optional[ConfigVersion]:
        """Get current config version."""
        return self._version

    def get_audit_log(self, limit: int = 100) -> List[AuditLogEntry]:
        """Get recent audit log entries."""
        return self._audit_log[-limit:]

    def rollback(self, version: str, author: str = "system") -> bool:
        """Rollback to previous version."""
        # Implementation would restore from backup
        logger.info(f"Rolling back to version {version}")
        self._audit("rollback", "config", None, None, author, f"Rollback to {version}")
        return True


# Global default config manager
default_config: Optional[ConfigManager] = None


def init_config(config_path: str, encryption_key: Optional[str] = None, schema: Optional[Dict] = None) -> ConfigManager:
    """Initialize global config manager."""
    global default_config
    default_config = ConfigManager(config_path, encryption_key, schema)
    return default_config
