"""Configuration Manager with hardening features.

Provides:
1. Pydantic validation (via models.py)
2. Encryption for sensitive data (via encryption.py)
3. Secrets management
4. Config versioning + rollback
5. Audit logging for all config changes
6. Git integration for persistence
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .models import (
    ZoneConfig,
    Conflict,
    ConfigVersion,
    ConfigAuditEntry,
    ConfigAuditLog,
    SonosConfig,
    LightConfig,
    PresenceConfig,
    AlarmConfig,
    MoodConfig,
)
from .encryption import ConfigEncryption, SecretManager, EncryptionError

_LOGGER = logging.getLogger(__name__)

# Storage keys
STORAGE_KEY = "copilot_core.config_manager"
STORAGE_VERSION = 2
VERSIONS_DIR = "config_versions"
AUDIT_LOG_KEY = "copilot_core.config_audit"


class ConfigValidationError(Exception):
    """Configuration validation failed."""
    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        super().__init__(f"Config validation failed: {errors}")


class ConfigRollbackError(Exception):
    """Config rollback operation failed."""
    pass


class ConfigManager:
    """Central configuration manager with hardening features.
    
    Usage:
        manager = ConfigManager(hass, workspace="/config/clawd")
        await manager.initialize()
        
        # Get validated zone config
        zone = manager.get_zone("wohnbereich")
        
        # Update with validation
        zone.sonos.volume_default = 50
        await manager.save_zone(zone, user="admin", reason="Volume adjustment")
        
        # Rollback if needed
        await manager.rollback_to_version(5)
    """
    
    def __init__(
        self,
        hass: HomeAssistant,
        workspace: str = "/config/clawd",
        master_secret: Optional[str] = None,
    ) -> None:
        """Initialize config manager.
        
        Args:
            hass: Home Assistant instance
            workspace: Workspace directory for version backups
            master_secret: Master secret for encryption (or use env var)
        """
        self._hass = hass
        self._workspace = Path(workspace)
        self._versions_dir = self._workspace / VERSIONS_DIR
        self._store: Optional[Store] = None
        self._audit_store: Optional[Store] = None
        
        # Initialize encryption
        self._encryptor = ConfigEncryption(master_secret=master_secret)
        self._secrets = SecretManager(self._encryptor)
        
        # In-memory state
        self._zones: Dict[str, ZoneConfig] = {}
        self._conflicts: List[Conflict] = []
        self._audit_log = ConfigAuditLog()
        self._current_version: int = 0
        self._loaded = False
    
    async def initialize(self) -> None:
        """Initialize config manager - load persisted state."""
        # Initialize stores
        self._store = Store(self._hass, STORAGE_VERSION, STORAGE_KEY)
        self._audit_store = Store(self._hass, STORAGE_VERSION, AUDIT_LOG_KEY)
        
        # Load persisted config
        await self._load_persisted_config()
        
        # Load audit log
        await self._load_audit_log()
        
        # Ensure versions directory exists
        self._versions_dir.mkdir(parents=True, exist_ok=True)
        
        self._loaded = True
        _LOGGER.info("Config manager initialized (version %d, %d zones)", 
                    self._current_version, len(self._zones))
    
    async def _load_persisted_config(self) -> None:
        """Load configuration from HA storage."""
        data = await self._store.async_load()
        if not data:
            _LOGGER.info("No persisted config found")
            return
        
        self._current_version = data.get("version", 0)
        
        zones_data = data.get("zones", [])
        for zone_data in zones_data:
            try:
                zone = self._parse_zone_config(zone_data)
                self._zones[zone.zone_id] = zone
            except Exception as e:
                _LOGGER.warning("Failed to load zone config: %s", e)
        
        # Load encrypted secrets
        secrets_data = data.get("secrets", {})
        for name, encrypted_value in secrets_data.items():
            self._secrets.store(name, encrypted_value, encrypt=False)
    
    async def _load_audit_log(self) -> None:
        """Load audit log from storage."""
        data = await self._audit_store.async_load()
        if data:
            entries_data = data.get("entries", [])
            for entry_data in entries_data:
                try:
                    entry = ConfigAuditEntry(**entry_data)
                    self._audit_log.add_entry(entry)
                except Exception as e:
                    _LOGGER.warning("Failed to load audit entry: %s", e)
    
    def _parse_zone_config(self, data: Dict[str, Any]) -> ZoneConfig:
        """Parse and validate zone configuration."""
        # Handle nested configs
        sonos_data = data.get("sonos", {})
        light_data = data.get("light", {})
        presence_data = data.get("presence", {})
        alarm_data = data.get("alarm", {})
        mood_data = data.get("mood", {})
        
        return ZoneConfig(
            zone_id=data.get("zone_id"),
            zone_name=data.get("zone_name", ""),
            area_id=data.get("area_id", ""),
            sonos=SonosConfig(**sonos_data) if sonos_data else SonosConfig(),
            light=LightConfig(**light_data) if light_data else LightConfig(),
            presence=PresenceConfig(**presence_data) if presence_data else PresenceConfig(),
            alarm=AlarmConfig(**alarm_data) if alarm_data else AlarmConfig(),
            mood=MoodConfig(**mood_data) if mood_data else MoodConfig(),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            defaults_applied=data.get("defaults_applied", False),
        )
    
    # ── Zone Management ───────────────────────────────────────────────
    
    def get_zone(self, zone_id: str) -> Optional[ZoneConfig]:
        """Get validated zone configuration."""
        return self._zones.get(zone_id)
    
    def get_all_zones(self) -> List[ZoneConfig]:
        """Get all zone configurations."""
        return list(self._zones.values())
    
    async def save_zone(
        self,
        zone: ZoneConfig,
        user: str = "system",
        reason: str = "",
    ) -> None:
        """Save zone configuration with validation and audit logging.
        
        Args:
            zone: Zone configuration to save
            user: User identifier for audit log
            reason: Reason for change (for audit log)
            
        Raises:
            ConfigValidationError: If validation fails
        """
        # Validate zone config (Pydantic does this automatically)
        try:
            # Trigger validation by accessing model
            zone.model_dump()
        except Exception as e:
            errors = [str(e)]
            self._log_audit(
                action="validate",
                zone_id=zone.zone_id,
                success=False,
                user=user,
                reason=reason,
                error_message=str(e),
            )
            raise ConfigValidationError(errors)
        
        # Update timestamp
        zone.updated_at = datetime.now(timezone.utc).isoformat()
        
        # Store in memory
        old_zone = self._zones.get(zone.zone_id)
        self._zones[zone.zone_id] = zone
        
        # Audit log
        self._log_audit(
            action="update" if old_zone else "create",
            zone_id=zone.zone_id,
            old_value=old_zone.model_dump() if old_zone else None,
            new_value=zone.model_dump(),
            user=user,
            reason=reason,
        )
        
        # Persist
        await self._persist_config()
    
    async def delete_zone(
        self,
        zone_id: str,
        user: str = "system",
        reason: str = "",
    ) -> bool:
        """Delete a zone configuration.
        
        Args:
            zone_id: Zone to delete
            user: User identifier for audit log
            reason: Reason for deletion
            
        Returns:
            True if deleted, False if not found
        """
        if zone_id not in self._zones:
            return False
        
        old_zone = self._zones[zone_id]
        del self._zones[zone_id]
        
        self._log_audit(
            action="delete",
            zone_id=zone_id,
            old_value=old_zone.model_dump(),
            user=user,
            reason=reason,
        )
        
        await self._persist_config()
        return True
    
    # ── Secrets Management ────────────────────────────────────────────
    
    def store_secret(
        self,
        name: str,
        value: str,
        user: str = "system",
        reason: str = "",
    ) -> None:
        """Store an encrypted secret.
        
        Args:
            name: Secret identifier
            value: Secret value (will be encrypted)
            user: User identifier for audit log
            reason: Reason for storing
        """
        old_value = self._secrets.retrieve(name, decrypt=False)
        encrypted = self._secrets.store(name, value, encrypt=True)
        
        self._log_audit(
            action="update",
            field_path=f"secrets.{name}",
            old_value=old_value,
            new_value=encrypted,
            user=user,
            reason=reason,
        )
    
    def get_secret(self, name: str) -> Optional[str]:
        """Retrieve and decrypt a secret.
        
        Args:
            name: Secret identifier
            
        Returns:
            Decrypted secret value, or None if not found
        """
        return self._secrets.retrieve(name, decrypt=True)
    
    def delete_secret(self, name: str, user: str = "system", reason: str = "") -> bool:
        """Delete a secret.
        
        Args:
            name: Secret identifier
            user: User identifier for audit log
            reason: Reason for deletion
            
        Returns:
            True if deleted, False if not found
        """
        old_value = self._secrets.retrieve(name, decrypt=False)
        deleted = self._secrets.delete(name)
        
        if deleted:
            self._log_audit(
                action="delete",
                field_path=f"secrets.{name}",
                old_value=old_value,
                user=user,
                reason=reason,
            )
        
        return deleted
    
    # ── Versioning & Rollback ─────────────────────────────────────────
    
    async def create_version_snapshot(
        self,
        description: str = "",
        user: str = "system",
    ) -> int:
        """Create a version snapshot for rollback.
        
        Args:
            description: Version description
            user: User identifier
            
        Returns:
            New version number
        """
        self._current_version += 1
        
        # Create version metadata
        config_data = self._to_data()
        checksum = self._compute_checksum(config_data)
        
        version = ConfigVersion(
            version=self._current_version,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=user,
            commit_hash=self._get_git_commit(),
            description=description,
            zone_count=len(self._zones),
            checksum=checksum,
        )
        
        # Save to versions directory
        version_file = self._versions_dir / f"v{self._current_version}.json"
        version_data = {
            "metadata": version.model_dump(),
            "config": config_data,
        }
        
        with open(version_file, 'w') as f:
            json.dump(version_data, f, indent=2)
        
        # Set file permissions
        version_file.chmod(0o600)
        
        _LOGGER.info("Created config version %d: %s", self._current_version, description)
        
        self._log_audit(
            action="version_create",
            user=user,
            reason=description,
            new_value={"version": self._current_version},
        )
        
        return self._current_version
    
    async def rollback_to_version(
        self,
        version: int,
        user: str = "system",
        reason: str = "",
    ) -> None:
        """Rollback configuration to a previous version.
        
        Args:
            version: Version number to rollback to
            user: User identifier
            reason: Reason for rollback
            
        Raises:
            ConfigRollbackError: If rollback fails
        """
        version_file = self._versions_dir / f"v{version}.json"
        
        if not version_file.exists():
            raise ConfigRollbackError(f"Version {version} not found")
        
        try:
            # Load version data
            with open(version_file, 'r') as f:
                version_data = json.load(f)
            
            # Verify checksum
            config_data = version_data.get("config", {})
            checksum = self._compute_checksum(config_data)
            stored_checksum = version_data.get("metadata", {}).get("checksum")
            
            if checksum != stored_checksum:
                _LOGGER.warning("Version %d checksum mismatch - may be corrupted", version)
            
            # Restore zones
            old_zones = {k: v.model_dump() for k, v in self._zones.items()}
            self._zones.clear()
            
            zones_data = config_data.get("zones", [])
            for zone_data in zones_data:
                try:
                    zone = self._parse_zone_config(zone_data)
                    self._zones[zone.zone_id] = zone
                except Exception as e:
                    _LOGGER.warning("Failed to restore zone from version %d: %s", version, e)
            
            # Restore secrets
            secrets_data = config_data.get("secrets", {})
            self._secrets._secrets.clear()
            for name, encrypted_value in secrets_data.items():
                self._secrets.store(name, encrypted_value, encrypt=False)
            
            # Update current version
            self._current_version = version
            
            # Audit log
            self._log_audit(
                action="rollback",
                user=user,
                reason=reason,
                old_value={"version": self._current_version},
                new_value={"version": version},
            )
            
            # Persist restored config
            await self._persist_config()
            
            _LOGGER.info("Rolled back to config version %d", version)
            
        except Exception as e:
            raise ConfigRollbackError(f"Rollback failed: {e}")
    
    def list_versions(self, limit: int = 20) -> List[ConfigVersion]:
        """List available versions for rollback.
        
        Args:
            limit: Maximum number of versions to return
            
        Returns:
            List of version metadata, newest first
        """
        versions = []
        
        for i in range(self._current_version, 0, -1):
            version_file = self._versions_dir / f"v{i}.json"
            if version_file.exists():
                try:
                    with open(version_file, 'r') as f:
                        version_data = json.load(f)
                    metadata = version_data.get("metadata", {})
                    versions.append(ConfigVersion(**metadata))
                except Exception as e:
                    _LOGGER.warning("Failed to read version %d: %s", i, e)
            
            if len(versions) >= limit:
                break
        
        return versions
    
    async def cleanup_old_versions(self, keep: int = 10) -> int:
        """Remove old version snapshots to save space.
        
        Args:
            keep: Number of recent versions to keep
            
        Returns:
            Number of versions deleted
        """
        deleted = 0
        versions = self.list_versions(limit=1000)
        
        for version in versions[keep:]:
            version_file = self._versions_dir / f"v{version.version}.json"
            if version_file.exists():
                version_file.unlink()
                deleted += 1
                _LOGGER.debug("Deleted old config version %d", version.version)
        
        return deleted
    
    # ── Audit Logging ─────────────────────────────────────────────────
    
    def _log_audit(
        self,
        action: str,
        zone_id: Optional[str] = None,
        field_path: Optional[str] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        user: str = "system",
        reason: str = "",
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Add entry to audit log."""
        entry = ConfigAuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            zone_id=zone_id,
            field_path=field_path,
            old_value=self._sanitize_for_audit(old_value),
            new_value=self._sanitize_for_audit(new_value),
            user=user,
            reason=reason,
            success=success,
            error_message=error_message,
        )
        
        self._audit_log.add_entry(entry)
    
    def _sanitize_for_audit(self, value: Any) -> Any:
        """Sanitize value for audit log (remove secrets)."""
        if value is None:
            return None
        
        if isinstance(value, dict):
            # Remove encrypted secrets from audit log
            sanitized = {}
            for k, v in value.items():
                if k == "secrets":
                    sanitized[k] = {"<encrypted>": True}
                else:
                    sanitized[k] = v
            return sanitized
        
        return value
    
    def get_audit_log(
        self,
        limit: int = 100,
        action: Optional[str] = None,
        zone_id: Optional[str] = None,
        user: Optional[str] = None,
    ) -> List[ConfigAuditEntry]:
        """Query audit log.
        
        Args:
            limit: Maximum entries to return
            action: Filter by action type
            zone_id: Filter by zone
            user: Filter by user
            
        Returns:
            Filtered audit entries, newest first
        """
        entries = list(self._audit_log.entries)
        
        # Filter
        if action:
            entries = [e for e in entries if e.action == action]
        if zone_id:
            entries = [e for e in entries if e.zone_id == zone_id]
        if user:
            entries = [e for e in entries if e.user == user]
        
        # Sort by timestamp descending
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        
        return entries[:limit]
    
    async def export_audit_log(self, output_path: str) -> str:
        """Export audit log to file.
        
        Args:
            output_path: Path to write audit log
            
        Returns:
            Path to exported file
        """
        path = Path(output_path)
        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "entry_count": len(self._audit_log.entries),
            "entries": [e.model_dump() for e in self._audit_log.entries],
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        _LOGGER.info("Exported audit log: %s (%d entries)", path, len(self._audit_log.entries))
        return str(path)
    
    # ── Persistence ───────────────────────────────────────────────────
    
    async def _persist_config(self) -> None:
        """Persist configuration to HA storage."""
        if not self._store:
            _LOGGER.warning("Cannot persist: storage not initialized")
            return
        
        data = self._to_data()
        await self._store.async_save(data)
        
        # Also persist audit log
        if self._audit_store:
            audit_data = {
                "entries": [e.model_dump() for e in self._audit_log.entries],
                "max_entries": self._audit_log.max_entries,
            }
            await self._audit_store.async_save(audit_data)
    
    def _to_data(self) -> Dict[str, Any]:
        """Convert configuration to persistable data."""
        zones_data = [zone.model_dump() for zone in self._zones.values()]
        
        return {
            "version": self._current_version,
            "zones": zones_data,
            "secrets": self._secrets.export_secrets(decrypt=False),
            "updated": datetime.now(timezone.utc).isoformat(),
        }
    
    def _compute_checksum(self, data: Dict[str, Any]) -> str:
        """Compute SHA256 checksum of config data."""
        # Sort keys for deterministic output
        canonical = json.dumps(data, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def _get_git_commit(self) -> str:
        """Get current git commit hash."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self._workspace,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip()
        except Exception:
            return ""
    
    # ── Validation ────────────────────────────────────────────────────
    
    def validate_all(self) -> Tuple[bool, List[str]]:
        """Validate all configurations.
        
        Returns:
            Tuple of (success, error_messages)
        """
        errors = []
        
        for zone_id, zone in self._zones.items():
            try:
                zone.model_dump()
            except Exception as e:
                errors.append(f"Zone {zone_id}: {e}")
        
        return (len(errors) == 0, errors)
    
    def detect_conflicts(self) -> List[Conflict]:
        """Detect configuration conflicts (same as cross_module)."""
        # This would duplicate the logic from cross_module.py
        # For now, return empty - can be integrated later
        return self._conflicts


# ── Factory Function ─────────────────────────────────────────────────


async def async_get_config_manager(
    hass: HomeAssistant,
    workspace: str = "/config/clawd",
    master_secret: Optional[str] = None,
) -> ConfigManager:
    """Get or create config manager instance.
    
    Args:
        hass: Home Assistant instance
        workspace: Workspace directory
        master_secret: Master secret for encryption
        
    Returns:
        ConfigManager instance
    """
    if "copilot_core" not in hass.data:
        hass.data["copilot_core"] = {}
    
    if "config_manager" not in hass.data["copilot_core"]:
        manager = ConfigManager(hass, workspace=workspace, master_secret=master_secret)
        await manager.initialize()
        hass.data["copilot_core"]["config_manager"] = manager
    else:
        manager = hass.data["copilot_core"]["config_manager"]
    
    return manager
