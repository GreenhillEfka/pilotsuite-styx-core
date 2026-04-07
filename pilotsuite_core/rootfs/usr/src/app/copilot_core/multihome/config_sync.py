"""Configuration Synchronization for Multi-Home Setup.

Handles synchronization of configuration data between multiple home instances,
including automations, zones, entities, and user preferences.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from .sync_engine import (
    SyncEngine,
    SyncOperation,
    SyncStatus,
    ConflictResolution,
    get_sync_engine,
    HomeInstance,
)

logger = logging.getLogger(__name__)


class ConfigSync:
    """Handles configuration synchronization between homes."""
    
    def __init__(self, sync_engine: Optional[SyncEngine] = None):
        """Initialize config sync."""
        self.sync_engine = sync_engine or get_sync_engine()
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._config_versions: Dict[str, str] = {}  # home_id -> version_hash
    
    def get_config_hash(self, config: Dict[str, Any]) -> str:
        """Generate hash for configuration data."""
        config_json = json.dumps(config, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(config_json.encode('utf-8')).hexdigest()[:16]
    
    def fetch_local_config(self, home_id: str) -> Dict[str, Any]:
        """Fetch local configuration for a home."""
        # In production, this would load from actual config files/database
        config = {
            "automations": [],
            "zones": [],
            "entities": [],
            "user_preferences": {},
            "location_settings": {},
            "schedules": [],
        }
        
        # Try to load from disk if available
        config_file = f"/data/multihome/configs/{home_id}.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config for {home_id}: {e}")
        
        self._config_cache[home_id] = config
        self._config_versions[home_id] = self.get_config_hash(config)
        return config
    
    def save_local_config(self, home_id: str, config: Dict[str, Any]) -> bool:
        """Save configuration locally."""
        try:
            config_dir = "/data/multihome/configs"
            os.makedirs(config_dir, exist_ok=True)
            
            config_file = f"{config_dir}/{home_id}.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            self._config_cache[home_id] = config
            self._config_versions[home_id] = self.get_config_hash(config)
            logger.info(f"Saved config for home {home_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config for {home_id}: {e}")
            return False
    
    def detect_config_changes(
        self,
        source_home_id: str,
        target_home_id: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        """Detect configuration changes between two homes."""
        source_config = self.fetch_local_config(source_home_id)
        target_config = self.fetch_local_config(target_home_id)
        
        added = []
        modified = []
        removed = []
        
        # Compare sections
        for section in ["automations", "zones", "entities", "schedules"]:
            source_items = {item.get("id"): item for item in source_config.get(section, [])}
            target_items = {item.get("id"): item for item in target_config.get(section, [])}
            
            # Find added items
            for item_id in source_items:
                if item_id not in target_items:
                    added.append(f"{section}.{item_id}")
                elif source_items[item_id] != target_items[item_id]:
                    modified.append(f"{section}.{item_id}")
            
            # Find removed items
            for item_id in target_items:
                if item_id not in source_items:
                    removed.append(f"{section}.{item_id}")
        
        # Compare user preferences
        source_prefs = source_config.get("user_preferences", {})
        target_prefs = target_config.get("user_preferences", {})
        
        for key in source_prefs:
            if key not in target_prefs:
                added.append(f"preferences.{key}")
            elif source_prefs[key] != target_prefs[key]:
                modified.append(f"preferences.{key}")
        
        for key in target_prefs:
            if key not in source_prefs:
                removed.append(f"preferences.{key}")
        
        changes = {
            "added": added,
            "modified": modified,
            "removed": removed,
            "source_version": self._config_versions.get(source_home_id),
            "target_version": self._config_versions.get(target_home_id),
        }
        
        logger.info(f"Detected config changes: {len(added)} added, {len(modified)} modified, {len(removed)} removed")
        return source_config, target_config, changes
    
    def create_config_sync_operation(
        self,
        source_home_id: str,
        target_home_id: str,
        sync_mode: str = "full"  # full, incremental, selective
    ) -> Optional[SyncOperation]:
        """Create a configuration synchronization operation."""
        source_config, target_config, changes = self.detect_config_changes(
            source_home_id, target_home_id
        )
        
        if not any(changes.values()) and sync_mode != "full":
            logger.info(f"No config changes detected between {source_home_id} and {target_home_id}")
            return None
        
        operation_data = {
            "sync_mode": sync_mode,
            "changes": changes,
            "source_config": source_config if sync_mode == "full" else None,
            "incremental_updates": [] if sync_mode == "incremental" else None,
        }
        
        if sync_mode == "incremental":
            # Only include changed items
            for change_path in changes["added"] + changes["modified"]:
                section, item_id = change_path.split(".", 1)
                if section in source_config:
                    if section == "preferences":
                        item_value = source_config["user_preferences"].get(item_id)
                    else:
                        items = {item.get("id"): item for item in source_config.get(section, [])}
                        item_value = items.get(item_id)
                    
                    if item_value:
                        operation_data["incremental_updates"].append({
                            "action": "update" if change_path in changes["modified"] else "add",
                            "section": section,
                            "item_id": item_id,
                            "value": item_value
                        })
            
            for change_path in changes["removed"]:
                section, item_id = change_path.split(".", 1)
                operation_data["incremental_updates"].append({
                    "action": "delete",
                    "section": section,
                    "item_id": item_id
                })
        
        operation = self.sync_engine.create_sync_operation(
            source_home_id=source_home_id,
            target_home_id=target_home_id,
            operation_type="config",
            data=operation_data
        )
        
        return operation
    
    def apply_config_sync(self, operation: SyncOperation) -> bool:
        """Apply configuration synchronization from an operation."""
        if operation.operation_type != "config":
            logger.error(f"Invalid operation type: {operation.operation_type}")
            return False
        
        try:
            target_home_id = operation.target_home_id
            sync_mode = operation.data.get("sync_mode", "full")
            
            # Get current target config
            target_config = self.fetch_local_config(target_home_id)
            
            if sync_mode == "full" and operation.data.get("source_config"):
                # Full replacement
                target_config = operation.data["source_config"]
            elif sync_mode == "incremental":
                # Apply incremental updates
                for update in operation.data.get("incremental_updates", []):
                    section = update["section"]
                    action = update["action"]
                    item_id = update.get("item_id")
                    value = update.get("value")
                    
                    if section == "preferences":
                        if action == "delete":
                            target_config["user_preferences"].pop(item_id, None)
                        else:
                            target_config["user_preferences"][item_id] = value
                    elif section in ["automations", "zones", "entities", "schedules"]:
                        items = target_config.get(section, [])
                        items_dict = {item.get("id"): item for item in items}
                        
                        if action == "delete":
                            items_dict.pop(item_id, None)
                        else:
                            items_dict[item_id] = value
                        
                        target_config[section] = list(items_dict.values())
            
            # Save updated config
            success = self.save_local_config(target_home_id, target_config)
            
            if success:
                operation.status = SyncStatus.COMPLETED
                operation.completed_at = datetime.now(timezone.utc)
                logger.info(f"Applied config sync to {target_home_id}")
            else:
                operation.status = SyncStatus.FAILED
                operation.error_message = "Failed to save configuration"
            
            return success
            
        except Exception as e:
            operation.status = SyncStatus.FAILED
            operation.error_message = str(e)
            logger.error(f"Failed to apply config sync: {e}")
            return False
    
    def sync_location_aware_automations(
        self,
        source_home_id: str,
        target_home_id: str,
        location_context: str
    ) -> Dict[str, Any]:
        """Synchronize location-aware automations (e.g., "Ferienhaus vorheizen")."""
        source_config = self.fetch_local_config(source_home_id)
        target_config = self.fetch_local_config(target_home_id)
        
        location_automations = []
        
        # Find automations tagged with location context
        for automation in source_config.get("automations", []):
            metadata = automation.get("metadata", {})
            if metadata.get("location_context") == location_context:
                location_automations.append(automation)
        
        # Merge into target config
        target_automations = target_config.get("automations", [])
        target_auto_ids = {a.get("id") for a in target_automations}
        
        merged_count = 0
        for auto in location_automations:
            if auto.get("id") not in target_auto_ids:
                target_automations.append(auto)
                merged_count += 1
        
        target_config["automations"] = target_automations
        self.save_local_config(target_home_id, target_config)
        
        logger.info(f"Merged {merged_count} location-aware automations for {location_context}")
        return {
            "merged_count": merged_count,
            "location_context": location_context,
            "target_home_id": target_home_id
        }
    
    def get_config_diff_report(
        self,
        home_id_1: str,
        home_id_2: str
    ) -> Dict[str, Any]:
        """Generate a configuration difference report between two homes."""
        config1 = self.fetch_local_config(home_id_1)
        config2 = self.fetch_local_config(home_id_2)
        
        _, _, changes = self.detect_config_changes(home_id_1, home_id_2)
        
        return {
            "home_1": home_id_1,
            "home_2": home_id_2,
            "home_1_version": self._config_versions.get(home_id_1),
            "home_2_version": self._config_versions.get(home_id_2),
            "changes": changes,
            "summary": {
                "total_added": len(changes["added"]),
                "total_modified": len(changes["modified"]),
                "total_removed": len(changes["removed"]),
            },
            "generated_at": datetime.now(timezone.utc).isoformat()
        }


# Singleton instance
_config_sync: Optional[ConfigSync] = None


def get_config_sync(sync_engine: Optional[SyncEngine] = None) -> ConfigSync:
    """Get or create the config sync singleton."""
    global _config_sync
    if _config_sync is None:
        _config_sync = ConfigSync(sync_engine)
    return _config_sync
