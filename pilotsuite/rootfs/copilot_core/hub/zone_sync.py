"""Zone Sync — Core HubZoneEngine ↔ HA Store V2 Synchronization.

Bidirectional sync between:
- Core: HabitusZoneEngine (in-memory, runtime)
- HA: HabitusZoneStoreV2 (persistent storage)

Features:
- Core → HA: Save zones to HA storage
- HA → Core: Load zones from HA storage
- Real-time sync via WebSocket events
- Conflict resolution (priority-based)
- Module state sync (active/learning/off)
- Tag-based entity assignment
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import aiohttp

_LOGGER = logging.getLogger(__name__)


class ZoneSyncClient:
    """Sync client for Core ↔ HA zone synchronization.
    
    Usage:
        sync = ZoneSyncClient(ha_url="http://homeassistant.local:8123")
        
        # Load zones from HA into Core
        await sync.load_from_ha()
        
        # Save Core zones to HA
        await sync.save_to_ha()
        
        # Trigger real-time sync
        await sync.trigger_sync()
    """
    
    def __init__(
        self,
        ha_url: str = "http://homeassistant.local:8123",
        ha_token: Optional[str] = None,
        core_url: str = "http://localhost:8909",
        timeout: int = 10,
    ):
        self.ha_url = ha_url.rstrip("/")
        self.ha_token = ha_token
        self.core_url = core_url.rstrip("/")
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {
                "Authorization": f"Bearer {self.ha_token}" if self.ha_token else "",
                "Content-Type": "application/json",
            }
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    # ======================================================================
    # HA → Core Sync
    # ======================================================================
    
    async def load_from_ha(self) -> Dict[str, Any]:
        """Load zones from HA Store V2 into Core HubZoneEngine.
        
        Returns:
            Sync result with zone count and status
        """
        session = await self._get_session()
        
        # Call HA WebSocket API to get zones
        url = f"{self.ha_url}/api/pilotsuite/habitus/zones"
        
        async with session.get(url) as resp:
            if resp.status == 404:
                # HA integration not available, use Core defaults
                _LOGGER.warning("HA integration not available, using Core defaults")
                return {"status": "core_defaults", "zones": []}
            
            resp.raise_for_status()
            data = await resp.json()
        
        zones = data.get("zones", [])
        
        # Push zones to Core HubZoneEngine
        core_url = f"{self.core_url}/api/v1/hub/zones/import"
        
        async with session.post(core_url, json={"zones": zones}) as resp:
            resp.raise_for_status()
            result = await resp.json()
        
        _LOGGER.info(f"Loaded {len(zones)} zones from HA into Core")
        
        return {
            "status": "success",
            "zones_loaded": len(zones),
            "result": result,
        }
    
    # ======================================================================
    # Core → HA Sync
    # ======================================================================
    
    async def save_to_ha(self) -> Dict[str, Any]:
        """Save Core HubZoneEngine zones to HA Store V2.
        
        Returns:
            Sync result with zone count and status
        """
        session = await self._get_session()
        
        # Get zones from Core HubZoneEngine
        core_url = f"{self.core_url}/api/v1/hub/zones"
        
        async with session.get(core_url) as resp:
            resp.raise_for_status()
            data = await resp.json()
        
        zones = data.get("zones", [])
        
        # Push zones to HA Store V2
        ha_url = f"{self.ha_url}/api/pilotsuite/habitus/zones/sync"
        
        async with session.post(ha_url, json={"zones": zones}) as resp:
            if resp.status == 404:
                _LOGGER.warning("HA integration not available for sync")
                return {"status": "ha_unavailable", "zones_saved": 0}
            
            resp.raise_for_status()
            result = await resp.json()
        
        _LOGGER.info(f"Saved {len(zones)} zones from Core to HA")
        
        return {
            "status": "success",
            "zones_saved": len(zones),
            "result": result,
        }
    
    # ======================================================================
    # Real-time Sync
    # ======================================================================
    
    async def trigger_sync(self) -> Dict[str, Any]:
        """Trigger real-time sync between Core and HA.
        
        This is called when:
        - Zone configuration changes
        - Entity assignments change
        - Module states change
        """
        session = await self._get_session()
        
        # Trigger bidirectional sync
        sync_url = f"{self.core_url}/api/v1/hub/zones/trigger_sync"
        
        async with session.post(sync_url) as resp:
            if resp.status == 404:
                return {"status": "sync_unavailable", "message": "Sync endpoint not available"}
            
            resp.raise_for_status()
            result = await resp.json()
        
        return result
    
    # ======================================================================
    # Module State Sync
    # ======================================================================
    
    async def sync_module_state(
        self,
        zone_id: str,
        module_id: str,
        state: str,  # active, learning, off
    ) -> Dict[str, Any]:
        """Sync module state between Core and HA.
        
        Args:
            zone_id: Zone identifier
            module_id: Module identifier (light, motion, etc.)
            state: Module state (active, learning, off)
        """
        session = await self._get_session()
        
        # Update Core
        core_url = f"{self.core_url}/api/v1/hub/zones/{zone_id}/modules/{module_id}"
        
        async with session.put(core_url, json={"state": state}) as resp:
            if resp.status == 404:
                return {"status": "core_unavailable", "message": "Core endpoint not available"}
            
            resp.raise_for_status()
            core_result = await resp.json()
        
        # Update HA
        ha_url = f"{self.ha_url}/api/pilotsuite/habitus/zones/{zone_id}/modules/{module_id}"
        
        async with session.put(ha_url, json={"state": state}) as resp:
            if resp.status == 404:
                _LOGGER.warning(f"HA module sync unavailable for {zone_id}/{module_id}")
                return {"status": "partial", "core_updated": True, "ha_updated": False}
            
            resp.raise_for_status()
            ha_result = await resp.json()
        
        _LOGGER.info(f"Synced module {module_id} state to {state} for zone {zone_id}")
        
        return {
            "status": "success",
            "zone_id": zone_id,
            "module_id": module_id,
            "state": state,
            "core_updated": True,
            "ha_updated": True,
        }
    
    # ======================================================================
    # Tag-based Entity Sync
    # ======================================================================
    
    async def sync_entity_tags(
        self,
        entity_id: str,
        tags: List[str],
    ) -> Dict[str, Any]:
        """Sync entity tags between Core and HA.
        
        Tags enable automatic zone assignment:
        - domain:light, domain:climate, etc.
        - zone_living, zone_bath, etc.
        - auto_assign, needs_review, manual_override
        
        Args:
            entity_id: Entity identifier (light.wohnzimmer)
            tags: List of tags
        """
        session = await self._get_session()
        
        # Update HA entity tags
        ha_url = f"{self.ha_url}/api/pilotsuite/tags/{entity_id}"
        
        async with session.put(ha_url, json={"tags": tags}) as resp:
            if resp.status == 404:
                return {"status": "ha_unavailable", "message": "HA tag endpoint not available"}
            
            resp.raise_for_status()
            result = await resp.json()
        
        _LOGGER.info(f"Synced tags for {entity_id}: {tags}")
        
        return {
            "status": "success",
            "entity_id": entity_id,
            "tags": tags,
        }
    
    async def get_entities_by_tag(
        self,
        tag: str,
    ) -> List[Dict[str, Any]]:
        """Get entities by tag.
        
        Args:
            tag: Tag to filter by (e.g., "zone_living", "domain:light")
        
        Returns:
            List of entities with matching tag
        """
        session = await self._get_session()
        
        ha_url = f"{self.ha_url}/api/pilotsuite/tags"
        params = {"tag": tag}
        
        async with session.get(ha_url, params=params) as resp:
            if resp.status == 404:
                return []
            
            resp.raise_for_status()
            data = await resp.json()
        
        return data.get("entities", [])


# =============================================================================
# Zone Sync API Endpoints (for Flask Blueprint)
# =============================================================================

def create_zone_sync_blueprint(ha_url: str, ha_token: str, core_url: str):
    """Create Flask blueprint for zone sync API endpoints."""
    from flask import Blueprint, jsonify, request
    
    sync_bp = Blueprint("zone_sync", __name__, url_prefix="/api/v1/hub/zones")
    sync_client = ZoneSyncClient(ha_url=ha_url, ha_token=ha_token, core_url=core_url)
    
    @sync_bp.route("/sync", methods=["POST"])
    def trigger_zone_sync():
        """Trigger bidirectional zone sync."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(sync_client.trigger_sync())
        return jsonify(result)
    
    @sync_bp.route("/load_from_ha", methods=["POST"])
    def load_zones_from_ha():
        """Load zones from HA into Core."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(sync_client.load_from_ha())
        return jsonify(result)
    
    @sync_bp.route("/save_to_ha", methods=["POST"])
    def save_zones_to_ha():
        """Save Core zones to HA."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(sync_client.save_to_ha())
        return jsonify(result)
    
    @sync_bp.route("/<zone_id>/modules/<module_id>", methods=["PUT"])
    def update_module_state(zone_id: str, module_id: str):
        """Update module state for a zone."""
        import asyncio
        data = request.get_json()
        state = data.get("state", "learning")
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            sync_client.sync_module_state(zone_id, module_id, state)
        )
        return jsonify(result)
    
    @sync_bp.route("/tags/<path:entity_id>", methods=["PUT"])
    def update_entity_tags(entity_id: str):
        """Update entity tags."""
        import asyncio
        data = request.get_json()
        tags = data.get("tags", [])
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            sync_client.sync_entity_tags(entity_id, tags)
        )
        return jsonify(result)
    
    @sync_bp.route("/tags", methods=["GET"])
    def get_entities_by_tag_route():
        """Get entities by tag."""
        import asyncio
        tag = request.args.get("tag", "")
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        entities = loop.run_until_complete(
            sync_client.get_entities_by_tag(tag)
        )
        return jsonify({"entities": entities})
    
    return sync_bp
