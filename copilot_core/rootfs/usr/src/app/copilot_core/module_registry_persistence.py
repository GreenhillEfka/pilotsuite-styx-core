"""Module Registry Persistence (Slice 147).

Backup, restore, export and import functionality for module states.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from copilot_core.module_registry import ModuleRegistry

_LOGGER = logging.getLogger(__name__)

DEFAULT_BACKUP_DIR = Path("/data/backups")


class RegistryPersistence:
    """Persistence layer for ModuleRegistry."""

    def __init__(self, registry: ModuleRegistry, backup_dir: Path = DEFAULT_BACKUP_DIR):
        self._registry = registry
        self._backup_dir = backup_dir
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def export_to_json(self) -> Dict[str, Any]:
        """Export all module states to JSON-serializable dict."""
        global_states = self._registry.get_all_states()
        zone_states = self._registry.get_all_zone_states()

        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "global_states": global_states,
            "zone_states": zone_states,
        }

    def export_to_file(self, filepath: Optional[Path] = None) -> Path:
        """Export module states to JSON file."""
        if filepath is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filepath = self._backup_dir / f"module_registry_{timestamp}.json"

        data = self.export_to_json()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        _LOGGER.info("ModuleRegistry exported to %s", filepath)
        return filepath

    def import_from_json(self, data: Dict[str, Any]) -> Dict[str, int]:
        """Import module states from JSON dict."""
        stats = {"global_set": 0, "zone_set": 0, "errors": 0}

        # Import global states
        for module_id, state in data.get("global_states", {}).items():
            try:
                if self._registry.set_state(module_id, state):
                    stats["global_set"] += 1
            except Exception as exc:
                _LOGGER.warning("Failed to set state for %s: %s", module_id, exc)
                stats["errors"] += 1

        # Import zone states
        for zone_id, modules in data.get("zone_states", {}).items():
            for module_id, state in modules.items():
                try:
                    if self._registry.set_zone_state(zone_id, module_id, state):
                        stats["zone_set"] += 1
                except Exception as exc:
                    _LOGGER.warning("Failed to set zone state for %s/%s: %s", zone_id, module_id, exc)
                    stats["errors"] += 1

        _LOGGER.info("ModuleRegistry imported: %s", stats)
        return stats

    def import_from_file(self, filepath: Path) -> Dict[str, int]:
        """Import module states from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.import_from_json(data)

    def create_backup(self, name: Optional[str] = None) -> Path:
        """Create timestamped backup of module registry."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        name = name or f"backup_{timestamp}"
        filepath = self._backup_dir / f"{name}.json"
        return self.export_to_file(filepath)

    def list_backups(self) -> list[Dict[str, Any]]:
        """List available backups."""
        backups = []
        for filepath in self._backup_dir.glob("*.json"):
            try:
                stat = filepath.stat()
                backups.append({
                    "filename": filepath.name,
                    "path": str(filepath),
                    "size_bytes": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                })
            except Exception as exc:
                _LOGGER.debug("Failed to stat backup %s: %s", filepath, exc)
        return sorted(backups, key=lambda x: x["created"], reverse=True)

    def restore_backup(self, filename: str) -> bool:
        """Restore from backup file."""
        filepath = self._backup_dir / filename
        if not filepath.exists():
            _LOGGER.error("Backup not found: %s", filename)
            return False

        # Create pre-restore backup for safety
        self.create_backup("pre_restore")

        try:
            self.import_from_file(filepath)
            _LOGGER.info("ModuleRegistry restored from %s", filename)
            return True
        except Exception as exc:
            _LOGGER.error("Failed to restore backup: %s", exc)
            return False

    def auto_backup(self, max_backups: int = 10) -> Optional[Path]:
        """Create auto backup and cleanup old ones."""
        # Cleanup old backups
        backups = self.list_backups()
        if len(backups) > max_backups:
            for old_backup in backups[max_backups:]:
                try:
                    Path(old_backup["path"]).unlink()
                    _LOGGER.debug("Deleted old backup: %s", old_backup["filename"])
                except Exception as exc:
                    _LOGGER.warning("Failed to delete old backup: %s", exc)

        return self.create_backup("auto")
