"""Registry Persistence API (Slice 147).

Backup, restore, and export/import for ModuleRegistry.
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from pathlib import Path
from typing import Any, Dict

_LOGGER = logging.getLogger(__name__)

registry_persistence_bp = Blueprint("registry_persistence", __name__, url_prefix="/api/v1/registry")


@registry_persistence_bp.route("/backup", methods=["POST"])
def create_backup():
    """Create a backup of the module registry."""
    try:
        from copilot_core.module_registry_persistence import RegistryPersistence
        from copilot_core.module_registry import ModuleRegistry
        
        registry = ModuleRegistry()
        persistence = RegistryPersistence(registry)
        
        filepath = persistence.create_backup()
        
        return jsonify({
            "success": True,
            "backup_path": str(filepath),
            "timestamp": Path(filepath).stem.replace("backup_", ""),
        })
    except Exception as exc:
        _LOGGER.error("Failed to create backup: %s", exc)
        return jsonify({"error": str(exc)}), 500


@registry_persistence_bp.route("/backups", methods=["GET"])
def list_backups():
    """List available registry backups."""
    try:
        from copilot_core.module_registry_persistence import RegistryPersistence
        from copilot_core.module_registry import ModuleRegistry
        
        registry = ModuleRegistry()
        persistence = RegistryPersistence(registry)
        
        backups = persistence.list_backups()
        
        return jsonify({
            "backups": backups,
            "count": len(backups),
        })
    except Exception as exc:
        _LOGGER.error("Failed to list backups: %s", exc)
        return jsonify({"error": str(exc)}), 500


@registry_persistence_bp.route("/restore", methods=["POST"])
def restore_backup():
    """Restore from a backup file."""
    data = request.get_json()
    filename = data.get("filename") if data else None
    
    if not filename:
        return jsonify({"error": "Missing 'filename'"}), 400
    
    try:
        from copilot_core.module_registry_persistence import RegistryPersistence
        from copilot_core.module_registry import ModuleRegistry
        
        registry = ModuleRegistry()
        persistence = RegistryPersistence(registry)
        
        success = persistence.restore_backup(filename)
        
        return jsonify({
            "success": success,
            "filename": filename,
        })
    except Exception as exc:
        _LOGGER.error("Failed to restore backup: %s", exc)
        return jsonify({"error": str(exc)}), 500


@registry_persistence_bp.route("/export", methods=["GET"])
def export_registry():
    """Export registry to JSON file."""
    try:
        from copilot_core.module_registry_persistence import RegistryPersistence
        from copilot_core.module_registry import ModuleRegistry
        
        registry = ModuleRegistry()
        persistence = RegistryPersistence(registry)
        
        filepath = persistence.export_to_file()
        
        return jsonify({
            "success": True,
            "export_path": str(filepath),
        })
    except Exception as exc:
        _LOGGER.error("Failed to export registry: %s", exc)
        return jsonify({"error": str(exc)}), 500
