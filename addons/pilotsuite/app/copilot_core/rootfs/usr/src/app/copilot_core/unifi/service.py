"""
UniFi Network Monitoring Service

Monitors UniFi network status:
- WAN uplink status (online/offline, latency, packet loss)
- Client roaming events
- Traffic baselines
- Integration with HA entity state
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class WANStatus:
    """WAN uplink status snapshot."""
    online: bool
    latency_ms: float = 0.0
    packet_loss_percent: float = 0.0
    uptime_seconds: int = 0
    ip_address: Optional[str] = None
    gateway: Optional[str] = None
    dns_servers: List[str] = field(default_factory=list)
    last_check: str = ""


@dataclass
class ClientDevice:
    """UniFi client device."""
    mac: str
    name: str
    ip: Optional[str]
    status: str  # online, offline, roaming
    device_type: str  # phone, laptop, iot, etc
    connected_ap: Optional[str]
    signal_dbm: Optional[int]
    roaming: bool
    last_seen: str


@dataclass
class RoamEvent:
    """Client roaming event."""
    client_mac: str
    client_name: str
    from_ap: str
    to_ap: str
    timestamp: str
    signal_strength: Optional[int]


@dataclass
class TrafficBaselines:
    """Traffic baseline metrics."""
    period: str  # hourly, daily, weekly
    avg_upload_mbps: float = 0.0
    avg_download_mbps: float = 0.0
    peak_upload_mbps: float = 0.0
    peak_download_mbps: float = 0.0
    total_bytes_up: int = 0
    total_bytes_down: int = 0
    last_updated: str = ""


@dataclass
class UniFiSnapshot:
    """Complete UniFi network snapshot."""
    wan: WANStatus
    clients: List[ClientDevice]
    roaming_events: List[RoamEvent]
    baselines: TrafficBaselines
    suppress_suggestions: bool
    suppression_reason: Optional[str]
    timestamp: str


class UniFiService:
    """
    UniFi network monitoring service.
    
    Provides network context for PilotSuite:
    - Detect network instability (affects all automations)
    - Client roaming patterns (location context)
    - Traffic anomalies (energy-saving opportunities)
    """
    
    def __init__(self, hass=None, config: Optional[Dict] = None):
        """
        Initialize UniFi service.
        
        Args:
            hass: Home Assistant instance (optional, for entity access)
            config: Service configuration dict
        """
        self.hass = hass
        self.config = config or {}
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes
        self._last_update: Optional[datetime] = None
        
        # Default thresholds
        self._latency_threshold_ms = self.config.get('latency_threshold_ms', 100)
        self._packet_loss_threshold = self.config.get('packet_loss_threshold', 2.0)
        self._roam_history_hours = self.config.get('roam_history_hours', 24)
    
    async def _ensure_update(self) -> None:
        """Ensure data is fresh (lazy update)."""
        now = datetime.utcnow()
        if self._last_update is None or (now - self._last_update).total_seconds() > self._cache_ttl:
            await self.update()
    
    async def update(self) -> UniFiSnapshot:
        """
        Update all UniFi network data.
        
        Returns:
            UniFiSnapshot with current network status
        """
        self._last_update = datetime.utcnow()
        
        # Gather data from available sources
        wan = await self._get_wan_status()
        clients = await self._get_clients()
        roams = await self._get_roaming_events()
        baselines = await self._get_traffic_baselines()
        
        # Determine suppression
        suppress, reason = self._check_suppression(wan, roams)
        
        snapshot = UniFiSnapshot(
            wan=wan,
            clients=clients,
            roaming_events=roams,
            baselines=baselines,
            suppress_suggestions=suppress,
            suppression_reason=reason,
            timestamp=self._last_update.isoformat()
        )
        
        self._cache['snapshot'] = snapshot
        return snapshot
    
    async def _get_wan_status(self) -> WANStatus:
        """
        Get WAN uplink status.
        
        Sources (in priority order):
        1. UniFi Network API (via hass)
        2. HA entity states (sensor.unifi_wan_*)
        3. Mock/simulated data
        """
        # Try UniFi entities via HA
        if self.hass:
            wan_state = self.hass.states.get('sensor.unifi_wan_status')
            if wan_state and wan_state.state == 'online':
                latency = 0.0
                latency_entity = self.hass.states.get('sensor.unifi_wan_latency')
                if latency_entity:
                    try:
                        latency = float(latency_entity.state)
                    except (ValueError, TypeError):
                        pass
                
                packet_loss = 0.0
                pl_entity = self.hass.states.get('sensor.unifi_wan_packet_loss')
                if pl_entity:
                    try:
                        packet_loss = float(pl_entity.state)
                    except (ValueError, TypeError):
                        pass
                
                return WANStatus(
                    online=True,
                    latency_ms=latency,
                    packet_loss_percent=packet_loss,
                    last_check=datetime.utcnow().isoformat()
                )
        
        # Fallback: return offline status (will be updated when UniFi is configured)
        return WANStatus(
            online=False,
            latency_ms=0.0,
            packet_loss_percent=0.0,
            last_check=datetime.utcnow().isoformat()
        )
    
    async def _get_clients(self) -> List[ClientDevice]:
        """
        Get list of connected clients.
        
        Sources:
        1. UniFi Network API
        2. HA device_tracker entities
        """
        clients = []
        
        if self.hass:
            # Get device_tracker entities that look like UniFi clients
            for entity_id, state in self.hass.states.all():
                if entity_id.startswith('device_tracker.') and 'unifi' in entity_id.lower():
                    name = state.attributes.get('friendly_name', state.name)
                    if not name:
                        name = entity_id.replace('device_tracker.', '')
                    
                    mac = state.attributes.get('mac') or entity_id.split('.')[-1].replace('_', ':')
                    
                    # Determine device type from name/attributes
                    device_type = 'unknown'
                    name_lower = name.lower()
                    if any(x in name_lower for x in ['iphone', 'ipad', 'phone', 'mobile']):
                        device_type = 'phone'
                    elif any(x in name_lower for x in ['laptop', 'macbook', 'pc', 'computer']):
                        device_type = 'laptop'
                    elif any(x in name_lower for x in ['echo', 'alexa', 'google home', 'nest']):
                        device_type = 'iot'
                    
                    clients.append(ClientDevice(
                        mac=mac,
                        name=name,
                        ip=state.state if '.' in state.state else None,
                        status='online' if state.state == 'home' else 'offline',
                        device_type=device_type,
                        connected_ap=state.attributes.get('source_type'),
                        signal_dbm=state.attributes.get('signal_strength'),
                        roaming=False,
                        last_seen=state.last_updated.isoformat() if state.last_updated else ''
                    ))
        
        return clients
    
    async def _get_roaming_events(self) -> List[RoamEvent]:
        """
        Get recent roaming events.
        
        Reads from HA event bus (unifi_event entities) or UniFi API.
        """
        roams = []
        
        # In a real implementation, this would query UniFi API
        # For now, return empty list (data comes from event bus)
        return roams
    
    async def _get_traffic_baselines(self) -> TrafficBaselines:
        """
        Get traffic baselines.
        
        Calculates from historical data or returns defaults.
        """
        # Default baselines (will be populated from UniFi API stats)
        return TrafficBaselines(
            period='daily',
            avg_upload_mbps=10.0,
            avg_download_mbps=100.0,
            peak_upload_mbps=50.0,
            peak_download_mbps=500.0,
            last_updated=datetime.utcnow().isoformat()
        )
    
    def _check_suppression(self, wan: WANStatus, roams: List[RoamEvent]) -> tuple:
        """
        Check if network context should suppress suggestions.
        
        Args:
            wan: Current WAN status
            roams: Recent roaming events
            
        Returns:
            (suppress: bool, reason: Optional[str])
        """
        # Suppress if WAN is down or unstable
        if not wan.online:
            return True, "WAN uplink offline"
        
        if wan.latency_ms > self._latency_threshold_ms:
            return True, f"High latency ({wan.latency_ms:.0f}ms > {self._latency_threshold_ms}ms)"
        
        if wan.packet_loss_percent > self._packet_loss_threshold:
            return True, f"Packet loss ({wan.packet_loss_percent:.1f}%)"
        
        # Check for recent roaming storms (client moving rapidly)
        recent_roams = [r for r in roams if 
            (datetime.utcnow() - datetime.fromisoformat(r.timestamp)).total_seconds() < 3600]
        
        if len(recent_roams) > 10:  # More than 10 roams in an hour
            return True, f"Client roaming storm ({len(recent_roams)} events/hour)"
        
        return False, None
    
    async def get_snapshot(self) -> UniFiSnapshot:
        """
        Get cached snapshot (refreshes if stale).
        """
        await self._ensure_update()
        return self._cache.get('snapshot') or await self.update()
    
    async def get_wan_status(self) -> WANStatus:
        """Get current WAN status."""
        snapshot = await self.get_snapshot()
        return snapshot.wan
    
    async def get_clients(self) -> List[ClientDevice]:
        """Get connected clients."""
        snapshot = await self.get_snapshot()
        return snapshot.clients
    
    async def get_roaming_events(self) -> List[RoamEvent]:
        """Get recent roaming events."""
        snapshot = await self.get_snapshot()
        return snapshot.roaming_events
    
    async def get_baselines(self) -> TrafficBaselines:
        """Get traffic baselines."""
        snapshot = await self.get_snapshot()
        return snapshot.baselines
    
    async def should_suppress_suggestions(self) -> tuple:
        """
        Check if network context suggests suppressing automation suggestions.
        
        Returns:
            (suppress: bool, reason: Optional[str])
        """
        snapshot = await self.get_snapshot()
        return snapshot.suppress_suggestions, snapshot.suppression_reason
    
    def get_suppression_info(self) -> Dict[str, Any]:
        """
        Get suppression info for suggestions.
        
        Returns dict suitable for passing to HA suggestions.
        """
        snapshot = self._cache.get('snapshot')
        if snapshot:
            return {
                'suppress': snapshot.suppress_suggestions,
                'reason': snapshot.suppression_reason,
                'wan_online': snapshot.wan.online,
                'client_count': len(snapshot.clients),
                'roam_count': len(snapshot.roaming_events)
            }
        return {
            'suppress': False,
            'reason': None,
            'wan_online': False,
            'client_count': 0,
            'roam_count': 0
        }
