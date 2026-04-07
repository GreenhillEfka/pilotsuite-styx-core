"""HACS Discovery API — Slice 180.

Exposes metadata for HACS to discover and install PilotSuite Core.
"""
from __future__ import annotations

import json
import logging
import os
from flask import Blueprint, jsonify
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("hacs_discovery", __name__, url_prefix="/api/hacs")

MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "copilot_core", "manifest.json")

@bp.get("/discovery")
def hacs_discovery():
    """Return HACS-compatible repository metadata.
    
    HACS polls this to discover available versions and installation info.
    """
    try:
        with open(MANIFEST_PATH, 'r') as f:
            manifest = json.load(f)
    except Exception as e:
        _LOGGER.warning(f"Failed to read manifest: {e}")
        manifest = {}

    return jsonify({
        "ok": True,
        "name": manifest.get("name", "PilotSuite Core"),
        "version": manifest.get("version", "unknown"),
        "description": manifest.get("description", ""),
        "homeassistant": manifest.get("homeassistant", "2024.1.0"),
        "repository": manifest.get("url", ""),
        "zip_release": manifest.get("zip_release", False),
        "filename": manifest.get("filename", "pilotsuite-styx-core.zip"),
        "manifest": manifest,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@bp.get("/versions")
def hacs_versions():
    """Return available versions for HACS."""
    # In production, this would query GitHub Releases API
    # For now, return current manifest version
    try:
        with open(MANIFEST_PATH, 'r') as f:
            manifest = json.load(f)
        current_version = manifest.get("version", "unknown")
    except Exception:
        current_version = "unknown"

    return jsonify({
        "ok": True,
        "versions": [current_version],
        "latest": current_version,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
