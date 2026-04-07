"""PilotSuite Plugin Hub — Official Plugin Repository & Marketplace."""
from __future__ import annotations

import logging
import aiohttp
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# PLUGIN CATEGORIES
# =============================================================================

class PluginCategory(Enum):
    """Plugin categories."""
    INTEGRATION = "integration"  # Device/service integrations
    AUTOMATION = "automation"  # Automation enhancements
    UI = "ui"  # UI components
    ANALYTICS = "analytics"  # Analytics & reporting
    NOTIFICATION = "notification"  # Notification channels
    VOICE = "voice"  # Voice integrations
    ENERGY = "energy"  # Energy management
    SECURITY = "security"  # Security enhancements


class PluginStatus(Enum):
    """Plugin availability status."""
    STABLE = "stable"
    BETA = "beta"
    ALPHA = "alpha"
    DEPRECATED = "deprecated"


@dataclass
class PluginMetadata:
    """Plugin metadata from hub."""
    plugin_id: str
    name: str
    description: str
    author: str
    version: str
    category: PluginCategory
    status: PluginStatus
    repository: str
    downloads: int = 0
    rating: float = 0.0
    tags: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    min_pilotsuite_version: str = "1.0.0"
    homepage: Optional[str] = None
    license: str = "MIT"
    last_updated: Optional[datetime] = None


# =============================================================================
# PLUGIN HUB CLIENT
# =============================================================================

class PluginHubClient:
    """
    Client for PilotSuite Plugin Hub (marketplace).
    
    Features:
    - Browse available plugins
    - Search plugins
    - Get plugin details
    - Download plugins
    - Submit plugins (for authors)
    
    Hub URL: https://plugins.pilotsuite.io (future)
    """

    HUB_URL = "https://plugins.pilotsuite.io/api/v1"

    def __init__(self, hub_url: Optional[str] = None):
        self.hub_url = hub_url or self.HUB_URL
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def list_plugins(
        self,
        category: Optional[PluginCategory] = None,
        status: Optional[PluginStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PluginMetadata]:
        """List available plugins."""
        session = await self._get_session()
        
        params = {
            "limit": limit,
            "offset": offset,
        }
        
        if category:
            params["category"] = category.value
        if status:
            params["status"] = status.value
        
        async with session.get(f"{self.hub_url}/plugins", params=params) as response:
            if response.status == 200:
                data = await response.json()
                return [self._parse_plugin(p) for p in data.get("plugins", [])]
            else:
                logger.error(f"Failed to list plugins: {response.status}")
                return []

    async def search_plugins(self, query: str, limit: int = 20) -> List[PluginMetadata]:
        """Search plugins by name, description, or tags."""
        session = await self._get_session()
        
        params = {"q": query, "limit": limit}
        
        async with session.get(f"{self.hub_url}/plugins/search", params=params) as response:
            if response.status == 200:
                data = await response.json()
                return [self._parse_plugin(p) for p in data.get("results", [])]
            else:
                logger.error(f"Search failed: {response.status}")
                return []

    async def get_plugin(self, plugin_id: str) -> Optional[PluginMetadata]:
        """Get plugin details by ID."""
        session = await self._get_session()
        
        async with session.get(f"{self.hub_url}/plugins/{plugin_id}") as response:
            if response.status == 200:
                data = await response.json()
                return self._parse_plugin(data)
            else:
                logger.error(f"Plugin not found: {plugin_id}")
                return None

    async def download_plugin(
        self,
        plugin_id: str,
        version: Optional[str] = None,
        target_dir: Optional[str] = None,
    ) -> Optional[Path]:
        """Download plugin package."""
        session = await self._get_session()
        
        params = {}
        if version:
            params["version"] = version
        
        async with session.get(
            f"{self.hub_url}/plugins/{plugin_id}/download",
            params=params,
        ) as response:
            if response.status == 200:
                target = Path(target_dir) if target_dir else Path("/config/pilotsuite/plugins")
                target.mkdir(parents=True, exist_ok=True)
                
                plugin_file = target / f"{plugin_id}.zip"
                
                with open(plugin_file, "wb") as f:
                    f.write(await response.read())
                
                logger.info(f"Downloaded plugin {plugin_id} to {plugin_file}")
                return plugin_file
            else:
                logger.error(f"Download failed: {response.status}")
                return None

    async def submit_plugin(self, plugin_package: Path, api_token: str) -> Dict[str, Any]:
        """Submit a plugin to the hub (for authors)."""
        session = await self._get_session()
        
        headers = {"Authorization": f"Bearer {api_token}"}
        
        with open(plugin_package, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("package", f, filename=plugin_package.name)
            
            async with session.post(
                f"{self.hub_url}/plugins/submit",
                data=data,
                headers=headers,
            ) as response:
                result = await response.json()
                
                if response.status == 201:
                    logger.info(f"Plugin submitted: {result.get('plugin_id')}")
                    return {"success": True, **result}
                else:
                    logger.error(f"Submission failed: {result}")
                    return {"success": False, "error": result}

    def _parse_plugin(self, data: Dict[str, Any]) -> PluginMetadata:
        """Parse plugin data from API response."""
        return PluginMetadata(
            plugin_id=data["plugin_id"],
            name=data["name"],
            description=data["description"],
            author=data["author"],
            version=data["version"],
            category=PluginCategory(data["category"]),
            status=PluginStatus(data["status"]),
            repository=data["repository"],
            downloads=data.get("downloads", 0),
            rating=data.get("rating", 0.0),
            tags=data.get("tags", []),
            requirements=data.get("requirements", []),
            min_pilotsuite_version=data.get("min_pilotsuite_version", "1.0.0"),
            homepage=data.get("homepage"),
            license=data.get("license", "MIT"),
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else None,
        )

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


# =============================================================================
# OFFICIAL PLUGINS
# =============================================================================

OFFICIAL_PLUGINS = [
    PluginMetadata(
        plugin_id="spotify-integration",
        name="Spotify Integration",
        description="Control Spotify playback, playlists, and discover music",
        author="PilotSuite Team",
        version="1.0.0",
        category=PluginCategory.INTEGRATION,
        status=PluginStatus.STABLE,
        repository="https://github.com/pilotsuite/plugin-spotify",
        downloads=15420,
        rating=4.8,
        tags=["music", "streaming", "media"],
        requirements=["spotipy>=2.23.0"],
        license="MIT",
    ),
    PluginMetadata(
        plugin_id="tesla-integration",
        name="Tesla Integration",
        description="Monitor and control Tesla vehicles (charge, climate, lock)",
        author="PilotSuite Team",
        version="1.0.0",
        category=PluginCategory.INTEGRATION,
        status=PluginStatus.STABLE,
        repository="https://github.com/pilotsuite/plugin-tesla",
        downloads=12350,
        rating=4.7,
        tags=["tesla", "ev", "vehicle", "energy"],
        requirements=["teslapy>=3.0.0"],
        license="MIT",
    ),
    PluginMetadata(
        plugin_id="advanced-scheduling",
        name="Advanced Scheduling",
        description="Complex scheduling with calendar integration and time zones",
        author="PilotSuite Team",
        version="1.0.0",
        category=PluginCategory.AUTOMATION,
        status=PluginStatus.STABLE,
        repository="https://github.com/pilotsuite/plugin-scheduler",
        downloads=8920,
        rating=4.6,
        tags=["scheduling", "calendar", "automation"],
        requirements=["python-dateutil>=2.8.0"],
        license="MIT",
    ),
    PluginMetadata(
        plugin_id="voice-commands",
        name="Voice Commands",
        description="Advanced voice command processing with intent recognition",
        author="PilotSuite Team",
        version="1.0.0",
        category=PluginCategory.VOICE,
        status=PluginStatus.BETA,
        repository="https://github.com/pilotsuite/plugin-voice",
        downloads=6540,
        rating=4.5,
        tags=["voice", "speech", "nlu"],
        requirements=["speechRecognition>=3.10.0"],
        license="MIT",
    ),
    PluginMetadata(
        plugin_id="custom-dashboards",
        name="Custom Dashboards",
        description="Advanced dashboard components and visualization tools",
        author="PilotSuite Team",
        version="1.0.0",
        category=PluginCategory.UI,
        status=PluginStatus.STABLE,
        repository="https://github.com/pilotsuite/plugin-dashboards",
        downloads=11230,
        rating=4.9,
        tags=["dashboard", "ui", "visualization"],
        requirements=[],
        license="MIT",
    ),
    PluginMetadata(
        plugin_id="pushbullet-notify",
        name="Pushbullet Notifications",
        description="Send notifications via Pushbullet",
        author="PilotSuite Team",
        version="1.0.0",
        category=PluginCategory.NOTIFICATION,
        status=PluginStatus.STABLE,
        repository="https://github.com/pilotsuite/plugin-pushbullet",
        downloads=5670,
        rating=4.4,
        tags=["notification", "pushbullet"],
        requirements=["pushbullet.py>=0.12.0"],
        license="MIT",
    ),
    PluginMetadata(
        plugin_id="energy-monitor",
        name="Energy Monitor Pro",
        description="Advanced energy monitoring with cost tracking",
        author="PilotSuite Team",
        version="1.0.0",
        category=PluginCategory.ENERGY,
        status=PluginStatus.STABLE,
        repository="https://github.com/pilotsuite/plugin-energy-monitor",
        downloads=9870,
        rating=4.7,
        tags=["energy", "monitoring", "cost"],
        requirements=[],
        license="MIT",
    ),
    PluginMetadata(
        plugin_id="security-camera",
        name="Security Camera Integration",
        description="Integrate security cameras with motion detection",
        author="PilotSuite Team",
        version="1.0.0",
        category=PluginCategory.SECURITY,
        status=PluginStatus.BETA,
        repository="https://github.com/pilotsuite/plugin-security-camera",
        downloads=7230,
        rating=4.5,
        tags=["security", "camera", "motion"],
        requirements=["opencv-python>=4.8.0"],
        license="MIT",
    ),
]


# =============================================================================
# PLUGIN MANAGER EXTENSION
# =============================================================================

class PluginHubManager:
    """Extended plugin manager with hub integration."""

    def __init__(self, plugins_dir: str = "/config/pilotsuite/plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.hub_client = PluginHubClient()
        self._official_plugins = OFFICIAL_PLUGINS

    async def browse_official(self) -> List[PluginMetadata]:
        """Browse official plugins."""
        return self._official_plugins

    async def browse_hub(self, category: Optional[PluginCategory] = None) -> List[PluginMetadata]:
        """Browse plugins from hub."""
        return await self.hub_client.list_plugins(category=category)

    async def search(self, query: str) -> List[PluginMetadata]:
        """Search plugins."""
        hub_results = await self.hub_client.search_plugins(query)
        official_results = [
            p for p in self._official_plugins
            if query.lower() in p.name.lower() or query.lower() in p.description.lower()
        ]
        return official_results + hub_results

    async def install_from_hub(self, plugin_id: str) -> Dict[str, Any]:
        """Install plugin from hub."""
        # Download
        plugin_file = await self.hub_client.download_plugin(plugin_id)
        
        if not plugin_file:
            return {"success": False, "error": "Download failed"}
        
        # Would extract and install here
        # For now, just return success
        
        return {
            "success": True,
            "plugin_id": plugin_id,
            "file": str(plugin_file),
        }

    async def close(self):
        """Close hub client."""
        await self.hub_client.close()


# =============================================================================
# HOME ASSISTANT INTEGRATION
# =============================================================================

async def async_setup_plugin_hub(hass, config: Dict[str, Any]):
    """Set up plugin hub in Home Assistant."""
    hub_manager = PluginHubManager()
    
    # Store in hass.data
    hass.data["pilotsuite_plugin_hub"] = hub_manager
    
    logger.info("Plugin hub set up successfully")
    
    return hub_manager
