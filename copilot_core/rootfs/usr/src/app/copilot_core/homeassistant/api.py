"""HomeAssistant Discovery API Endpoints.

Provides REST API for HA connection management and entity discovery:
- POST /api/v1/ha/connect — Establish HA connection
- GET /api/v1/ha/status — Connection status
- GET /api/v1/ha/areas — All areas/zones
- GET /api/v1/ha/entities — All entities (filtered)
- GET /api/v1/ha/entity/<entity_id> — Single entity
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from flask import Blueprint, jsonify, request

try:
    from copilot_core.api.security import require_token
except ImportError:
    from ..api.security import require_token
from .auto_discovery import AutoDiscovery, DiscoveredInstance
from .client import HomeAssistantClient, HAConnectionConfig
from .entity_mapper import EntityMapper, EntityMapping, WidgetType

logger = logging.getLogger(__name__)

ha_discovery_bp = Blueprint("ha_discovery", __name__)

# Global state (will be initialized properly in production)
_auto_discovery: Optional[AutoDiscovery] = None
_active_client: Optional[HomeAssistantClient] = None
_entity_mapper: Optional[EntityMapper] = None
_connection_lock = asyncio.Lock()


def init_ha_discovery_api() -> None:
    """Initialize HA discovery API state."""
    global _auto_discovery, _entity_mapper
    
    _auto_discovery = AutoDiscovery()
    _entity_mapper = EntityMapper()
    logger.info("HA Discovery API initialized")


async def _get_auto_discovery() -> AutoDiscovery:
    """Get or create auto-discovery instance."""
    global _auto_discovery
    
    if _auto_discovery is None:
        _auto_discovery = AutoDiscovery()
    
    return _auto_discovery


async def _get_entity_mapper() -> EntityMapper:
    """Get or create entity mapper instance."""
    global _entity_mapper
    
    if _entity_mapper is None:
        _entity_mapper = EntityMapper()
    
    return _entity_mapper


@ha_discovery_bp.route("/api/v1/ha/connect", methods=["POST"])
@require_token
async def connect_ha():
    """Establish connection to HomeAssistant.
    
    Request body:
    {
        "base_url": "http://homeassistant.local:8123",  // Optional
        "access_token": "your-long-lived-token",
        "verify_ssl": true,  // Optional, default true
        "timeout_seconds": 5.0  // Optional, default 5.0
    }
    
    Response:
    {
        "ok": true,
        "connected": true,
        "base_url": "...",
        "response_time_ms": 42.5,
        "version": "2024.1.0",
        "friendly_name": "Home Assistant"
    }
    """
    # global _active_client
    
    try:
        data = request.get_json() or {}
    except Exception:
        return jsonify({
            "ok": False,
            "error": "Invalid JSON body"
        }), 400
    
    base_url = data.get("base_url", "http://homeassistant.local:8123")
    access_token = data.get("access_token", "")
    verify_ssl = data.get("verify_ssl", True)
    timeout_seconds = data.get("timeout_seconds", 5.0)
    
    if not access_token:
        return jsonify({
            "ok": False,
            "error": "access_token is required"
        }), 400
    
    async with _connection_lock:
        # Close existing client
        if _active_client:
            await _active_client.close()
            _active_client = None
        
        # Create new connection
        try:
            discovery = await _get_auto_discovery()
            client = await discovery.connect(
                base_url=base_url,
                access_token=access_token,
                verify_ssl=verify_ssl,
                timeout_seconds=timeout_seconds
            )
            
            _active_client = client
            
            # Get instance info
            try:
                config = await client.get("/api/config")
                version = config.get("version", "")
                friendly_name = config.get("name", "Home Assistant")
            except Exception:
                version = ""
                friendly_name = "Home Assistant"
            
            logger.info(f"Connected to HA at {base_url} ({version})")
            
            return jsonify({
                "ok": True,
                "connected": True,
                "base_url": base_url,
                "response_time_ms": client.status.response_time_ms,
                "version": version,
                "friendly_name": friendly_name
            })
        
        except ConnectionError as e:
            logger.warning(f"Failed to connect to HA: {e}")
            return jsonify({
                "ok": False,
                "error": str(e)
            }), 503
        
        except Exception as e:
            logger.error(f"Unexpected error connecting to HA: {e}")
            return jsonify({
                "ok": False,
                "error": f"Connection failed: {str(e)}"
            }), 500


@ha_discovery_bp.route("/api/v1/ha/status", methods=["GET"])
@require_token
async def get_status():
    """Get current HA connection status.
    
    Response:
    {
        "ok": true,
        "connected": true,
        "base_url": "...",
        "response_time_ms": 42.5,
        "last_success": 1234567890.0,
        "last_error": null
    }
    """
    # global _active_client
    
    if _active_client is None:
        return jsonify({
            "ok": True,
            "connected": False,
            "message": "No active connection"
        })
    
    status = _active_client.status
    
    return jsonify({
        "ok": True,
        "connected": status.connected,
        "base_url": status.base_url,
        "response_time_ms": status.response_time_ms,
        "last_success": status.last_success,
        "last_error": status.last_error
    })


@ha_discovery_bp.route("/api/v1/ha/areas", methods=["GET"])
@require_token
async def get_areas():
    """Get all areas/zones from HomeAssistant.
    
    Response:
    {
        "ok": true,
        "count": 5,
        "areas": [
            {
                "area_id": "living_room",
                "name": "Living Room",
                ...
            }
        ]
    }
    """
    # global _active_client
    
    if _active_client is None:
        return jsonify({
            "ok": False,
            "error": "Not connected to HomeAssistant"
        }), 503
    
    try:
        areas = await _active_client.get_areas()
        
        # Update entity mapper with area registry
        mapper = await _get_entity_mapper()
        mapper.update_area_registry(areas)
        
        return jsonify({
            "ok": True,
            "count": len(areas),
            "areas": areas
        })
    
    except Exception as e:
        logger.error(f"Failed to get areas: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@ha_discovery_bp.route("/api/v1/ha/entities", methods=["GET"])
@require_token
async def get_entities():
    """Get all entities from HomeAssistant.
    
    Query params:
        domain: Filter by domain (e.g., "light", "sensor")
        area_id: Filter by area
        device_class: Filter by device class (for sensors)
    
    Response:
    {
        "ok": true,
        "count": 42,
        "entities": [
            {
                "entity_id": "light.living_room",
                "state": "on",
                "attributes": {...},
                "widget_type": "light",
                "name": "Living Room Light",
                "area_name": "Living Room",
                "icon": "mdi:lightbulb",
                "priority": 60
            }
        ]
    }
    """
    # global _active_client
    
    if _active_client is None:
        return jsonify({
            "ok": False,
            "error": "Not connected to HomeAssistant"
        }), 503
    
    try:
        # Get filter params
        domain_filter = request.args.get("domain")
        area_filter = request.args.get("area_id")
        device_class_filter = request.args.get("device_class")
        
        # Get all states
        states = await _active_client.get_states()
        
        # Apply filters
        filtered_states = []
        for state in states:
            if not isinstance(state, dict):
                continue
            
            entity_id = state.get("entity_id", "")
            attributes = state.get("attributes", {})
            
            # Domain filter
            if domain_filter:
                if not entity_id.startswith(f"{domain_filter}."):
                    continue
            
            # Area filter
            if area_filter:
                if attributes.get("area_id") != area_filter:
                    continue
            
            # Device class filter
            if device_class_filter:
                if attributes.get("device_class") != device_class_filter:
                    continue
            
            filtered_states.append(state)
        
        # Map entities to widgets
        mapper = await _get_entity_mapper()
        mappings = mapper.map_entities(filtered_states)
        
        # Convert to response format
        entities_data = []
        for mapping in mappings:
            entities_data.append({
                "entity_id": mapping.entity_id,
                "state": mapping.state,
                "attributes": mapping.attributes,
                "widget_type": mapping.widget_type.value,
                "name": mapping.name,
                "area_id": mapping.area_id,
                "area_name": mapping.area_name,
                "device_class": mapping.device_class,
                "unit_of_measurement": mapping.unit_of_measurement,
                "icon": mapping.icon,
                "priority": mapping.priority
            })
        
        return jsonify({
            "ok": True,
            "count": len(entities_data),
            "entities": entities_data
        })
    
    except Exception as e:
        logger.error(f"Failed to get entities: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@ha_discovery_bp.route("/api/v1/ha/entity/<entity_id>", methods=["GET"])
@require_token
async def get_entity(entity_id: str):
    """Get single entity from HomeAssistant.
    
    Response:
    {
        "ok": true,
        "entity": {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {...},
            "widget_type": "light",
            "name": "Living Room Light",
            ...
        }
    }
    """
    # global _active_client
    
    if _active_client is None:
        return jsonify({
            "ok": False,
            "error": "Not connected to HomeAssistant"
        }), 503
    
    try:
        # Get entity state
        state = await _active_client.get_entity(entity_id)
        
        if state is None:
            return jsonify({
                "ok": False,
                "error": f"Entity not found: {entity_id}"
            }), 404
        
        # Map entity to widget
        mapper = await _get_entity_mapper()
        mapping = mapper.map_entity(state)
        
        if mapping is None:
            return jsonify({
                "ok": False,
                "error": f"Failed to map entity: {entity_id}"
            }), 500
        
        return jsonify({
            "ok": True,
            "entity": {
                "entity_id": mapping.entity_id,
                "state": mapping.state,
                "attributes": mapping.attributes,
                "widget_type": mapping.widget_type.value,
                "name": mapping.name,
                "area_id": mapping.area_id,
                "area_name": mapping.area_name,
                "device_class": mapping.device_class,
                "unit_of_measurement": mapping.unit_of_measurement,
                "icon": mapping.icon,
                "priority": mapping.priority
            }
        })
    
    except FileNotFoundError:
        return jsonify({
            "ok": False,
            "error": f"Entity not found: {entity_id}"
        }), 404
    
    except Exception as e:
        logger.error(f"Failed to get entity {entity_id}: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@ha_discovery_bp.route("/api/v1/ha/discover", methods=["POST"])
@require_token
async def discover_ha():
    """Discover HomeAssistant instances.
    
    Request body (optional):
    {
        "configured_url": "http://homeassistant.local:8123",
        "timeout_seconds": 5.0
    }
    
    Response:
    {
        "ok": true,
        "count": 1,
        "instances": [
            {
                "base_url": "http://homeassistant.local:8123",
                "friendly_name": "Home Assistant",
                "version": "2024.1.0",
                "response_time_ms": 42.5,
                "requires_auth": true
            }
        ]
    }
    """
    try:
        data = request.get_json() or {}
    except Exception:
        data = {}
    
    configured_url = data.get("configured_url")
    timeout_seconds = data.get("timeout_seconds", 5.0)
    
    try:
        discovery = await _get_auto_discovery()
        instances = await discovery.discover(
            configured_url=configured_url,
            timeout_seconds=timeout_seconds
        )
        
        instances_data = [
            {
                "base_url": inst.base_url,
                "friendly_name": inst.friendly_name,
                "version": inst.version,
                "response_time_ms": inst.response_time_ms,
                "requires_auth": inst.requires_auth
            }
            for inst in instances
        ]
        
        return jsonify({
            "ok": True,
            "count": len(instances_data),
            "instances": instances_data
        })
    
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@ha_discovery_bp.route("/api/v1/ha/disconnect", methods=["POST"])
@require_token
async def disconnect_ha():
    """Disconnect from HomeAssistant.
    
    Response:
    {
        "ok": true,
        "message": "Disconnected"
    }
    """
    # global _active_client
    
    if _active_client:
        await _active_client.close()
        _active_client = None
        logger.info("Disconnected from HA")
    
    return jsonify({
        "ok": True,
        "message": "Disconnected"
    })
