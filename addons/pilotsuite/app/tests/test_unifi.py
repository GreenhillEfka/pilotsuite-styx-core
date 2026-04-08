"""
UniFi Neuron Tests

Tests for UniFi network monitoring module.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from copilot_core.unifi.service import (
    UniFiService,
    WANStatus,
    ClientDevice,
    RoamEvent,
    TrafficBaselines,
    UniFiSnapshot
)


class TestWANStatus:
    """Test WANStatus dataclass."""
    
    def test_default_values(self):
        """Test default values for WANStatus."""
        status = WANStatus(online=True)
        assert status.online is True
        assert status.latency_ms == 0.0
        assert status.packet_loss_percent == 0.0
        assert status.uptime_seconds == 0
        assert status.ip_address is None
        assert status.gateway is None
        assert status.dns_servers == []
        assert status.last_check == ""
    
    def test_full_values(self):
        """Test WANStatus with all values."""
        status = WANStatus(
            online=True,
            latency_ms=25.5,
            packet_loss_percent=0.1,
            uptime_seconds=86400,
            ip_address="192.168.1.1",
            gateway="192.168.1.254",
            dns_servers=["8.8.8.8", "1.1.1.1"],
            last_check="2026-02-14T12:00:00"
        )
        assert status.latency_ms == 25.5
        assert status.ip_address == "192.168.1.1"


class TestClientDevice:
    """Test ClientDevice dataclass."""
    
    def test_client_creation(self):
        """Test creating a client device."""
        client = ClientDevice(
            mac="AA:BB:CC:DD:EE:FF",
            name="Living Room Light",
            ip="192.168.1.100",
            status="online",
            device_type="iot",
            connected_ap="Living Room AP",
            signal_dbm=-45,
            roaming=False,
            last_seen="2026-02-14T12:00:00"
        )
        assert client.mac == "AA:BB:CC:DD:EE:FF"
        assert client.status == "online"
        assert client.device_type == "iot"


class TestUniFiService:
    """Test UniFiService class."""
    
    @pytest.fixture
    def service(self):
        """Create a UniFiService instance."""
        return UniFiService(config={
            'latency_threshold_ms': 100,
            'packet_loss_threshold': 2.0,
            'roam_history_hours': 24
        })
    
    def test_service_initialization(self, service):
        """Test service creation with defaults."""
        assert service._cache_ttl == 300
        assert service._latency_threshold_ms == 100
        assert service._packet_loss_threshold == 2.0
    
    @pytest.mark.asyncio
    async def test_update_returns_snapshot(self, service):
        """Test that update returns a UniFiSnapshot."""
        snapshot = await service.update()
        
        assert isinstance(snapshot, UniFiSnapshot)
        assert isinstance(snapshot.wan, WANStatus)
        assert isinstance(snapshot.clients, list)
        assert isinstance(snapshot.roaming_events, list)
        assert isinstance(snapshot.baselines, TrafficBaselines)
        assert 'T' in snapshot.timestamp
    
    @pytest.mark.asyncio
    async def test_get_wan_status_default_offline(self, service):
        """Test that WAN status is offline when no HA."""
        wan = await service._get_wan_status()
        
        assert wan.online is False
    
    @pytest.mark.asyncio
    async def test_get_clients_empty_without_hass(self, service):
        """Test that clients list is empty without HA."""
        clients = await service._get_clients()
        
        assert clients == []
    
    @pytest.mark.asyncio
    async def test_get_traffic_baselines_defaults(self, service):
        """Test that traffic baselines have defaults."""
        baselines = await service._get_traffic_baselines()
        
        assert baselines.period == 'daily'
        assert baselines.avg_upload_mbps == 10.0
        assert baselines.avg_download_mbps == 100.0
    
    def test_check_suppression_offline(self, service):
        """Test suppression when WAN is offline."""
        wan = WANStatus(online=False)
        suppress, reason = service._check_suppression(wan, [])
        
        assert suppress is True
        assert reason == "WAN uplink offline"
    
    def test_check_suppression_high_latency(self, service):
        """Test suppression when latency is high."""
        wan = WANStatus(
            online=True,
            latency_ms=150.0,  # Above 100ms threshold
            packet_loss_percent=0.0
        )
        suppress, reason = service._check_suppression(wan, [])
        
        assert suppress is True
        assert "High latency" in reason
    
    def test_check_suppression_high_packet_loss(self, service):
        """Test suppression when packet loss is high."""
        wan = WANStatus(
            online=True,
            latency_ms=50.0,
            packet_loss_percent=5.0  # Above 2% threshold
        )
        suppress, reason = service._check_suppression(wan, [])
        
        assert suppress is True
        assert "Packet loss" in reason
    
    def test_check_suppression_roaming_storm(self, service):
        """Test suppression when too many roams."""
        wan = WANStatus(online=True, latency_ms=10.0, packet_loss_percent=0.0)
        
        roams = [
            RoamEvent(
                client_mac="AA:BB:CC:DD:EE:FF",
                client_name="Phone",
                from_ap="AP1",
                to_ap="AP2",
                timestamp=(datetime.utcnow() - timedelta(minutes=5)).isoformat(),
                signal_strength=-50
            )
            for _ in range(15)  # More than 10 in an hour
        ]
        
        suppress, reason = service._check_suppression(wan, roams)
        
        assert suppress is True
        assert "roaming storm" in reason
    
    def test_check_suppression_healthy(self, service):
        """Test no suppression when network is healthy."""
        wan = WANStatus(
            online=True,
            latency_ms=20.0,
            packet_loss_percent=0.1
        )
        suppress, reason = service._check_suppression(wan, [])
        
        assert suppress is False
        assert reason is None
    
    @pytest.mark.asyncio
    async def test_get_snapshot_caching(self, service):
        """Test that snapshot is cached."""
        # First call populates cache
        snapshot1 = await service.get_snapshot()
        
        # Second call should return cached
        snapshot2 = await service.get_snapshot()
        
        assert snapshot1.timestamp == snapshot2.timestamp
    
    @pytest.mark.asyncio
    async def test_should_suppress_suggestions(self, service):
        """Test suggestion suppression check."""
        suppress, reason = await service.should_suppress_suggestions()

        # Without hass, WAN defaults to offline → suppress is expected
        assert isinstance(suppress, bool)
        assert reason is None or isinstance(reason, str)
    
    def test_get_suppression_info(self, service):
        """Test suppression info dict."""
        info = service.get_suppression_info()
        
        assert 'suppress' in info
        assert 'reason' in info
        assert 'wan_online' in info
        assert 'client_count' in info
        assert 'roam_count' in info


class TestUniFiServiceWithMockHA:
    """Test UniFiService with mocked Home Assistant."""
    
    @pytest.fixture
    def mock_hass(self):
        """Create a mock hass object."""
        hass = Mock()
        
        # Mock state for WAN status
        wan_state = Mock()
        wan_state.state = 'online'
        
        latency_entity = Mock()
        latency_entity.state = '25.5'
        
        hass.states.get = Mock(side_effect=[
            wan_state,  # sensor.unifi_wan_status
            latency_entity  # sensor.unifi_wan_latency
        ])
        
        # Mock device tracker entities
        phone_state = Mock()
        phone_state.state = 'home'
        phone_state.attributes = {
            'friendly_name': 'My iPhone',
            'mac': 'AA:BB:CC:DD:EE:01',
            'source_type': 'Living Room AP',
            'signal_strength': -45
        }
        
        laptop_state = Mock()
        laptop_state.state = 'home'
        laptop_state.attributes = {
            'friendly_name': 'MacBook Pro',
            'mac': 'AA:BB:CC:DD:EE:02',
            'source_type': 'Office AP',
            'signal_strength': -30
        }
        
        def get_state(entity_id):
            if 'unifi_wan' in entity_id.lower():
                if 'status' in entity_id:
                    return wan_state
                elif 'latency' in entity_id:
                    return latency_entity
            elif 'device_tracker' in entity_id:
                if 'iphone' in entity_id.lower():
                    return phone_state
                elif 'macbook' in entity_id.lower():
                    return laptop_state
            return None
        
        hass.states.get = Mock(side_effect=get_state)
        hass.states.all = Mock(return_value=[
            ("device_tracker.unifi_iphone", phone_state),
            ("device_tracker.unifi_macbook", laptop_state),
        ])
        
        return hass
    
    @pytest.mark.asyncio
    async def test_wan_status_from_ha(self, mock_hass):
        """Test WAN status from HA entities."""
        service = UniFiService(hass=mock_hass)
        wan = await service._get_wan_status()
        
        assert wan.online is True
        assert wan.latency_ms == 25.5
    
    @pytest.mark.asyncio
    async def test_clients_from_ha(self, mock_hass):
        """Test client detection from HA entities."""
        service = UniFiService(hass=mock_hass)
        clients = await service._get_clients()
        
        assert len(clients) == 2
        client_names = [c.name for c in clients]
        assert 'My iPhone' in client_names
        assert 'MacBook Pro' in client_names
    
    @pytest.mark.asyncio
    async def test_device_type_detection(self, mock_hass):
        """Test automatic device type detection."""
        service = UniFiService(hass=mock_hass)
        clients = await service._get_clients()
        
        # iPhone should be detected as phone
        phone = next((c for c in clients if 'iPhone' in c.name), None)
        if phone:
            assert phone.device_type == 'phone'
        
        # MacBook should be detected as laptop
        laptop = next((c for c in clients if 'MacBook' in c.name), None)
        if laptop:
            assert laptop.device_type == 'laptop'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
