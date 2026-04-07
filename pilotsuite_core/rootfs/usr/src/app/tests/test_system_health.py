"""
Tests for SystemHealth Neuron module.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class MockState:
    """Mock HA State object."""
    def __init__(self, entity_id, state, attributes=None):
        self.entity_id = entity_id
        self.state = state
        self.attributes = attributes or {}
        self.domain = entity_id.split('.')[0] if '.' in entity_id else 'unknown'


class MockHass:
    """Mock Home Assistant hass object."""
    def __init__(self):
        self.states = MockStateStore()
        self.services = MockServiceStore()


class MockStateStore:
    """Mock HA state store."""
    def __init__(self):
        self._states = {}
    
    def async_all(self):
        return list(self._states.values())
    
    def add(self, state):
        self._states[state.entity_id] = state


class MockServiceStore:
    """Mock HA service store."""
    def __init__(self):
        self._services = {}


class TestSystemHealthService:
    """Test SystemHealthService class."""
    
    def test_service_initialization(self):
        """Test service can be initialized with hass."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        assert service.hass == hass
        assert service._cache is not None
        assert service._cache_ttl == 300
    
    def test_get_zigbee_health_no_zha(self):
        """Test Zigbee health when no ZHA integration exists."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        result = service._get_zigbee_health()
        
        assert result['status'] == 'healthy'
        assert result['device_count'] == 0
        assert result['unavailable_devices'] == 0
    
    def test_get_zigbee_health_with_devices(self):
        """Test Zigbee health with devices present."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        
        # Add mock ZHA entities
        hass.states.add(MockState('zha.device', 'online', {'friendly_name': 'Coordinator'}))
        hass.states.add(MockState('zha.network', 'online'))
        # Add 10 devices, 1 unavailable (10% - still healthy)
        for i in range(9):
            hass.states.add(MockState(f'zha.device_{i}', 'online', {'friendly_name': f'Device {i}'}))
        hass.states.add(MockState('zha.device_unavail', 'unavailable', {'friendly_name': 'Sensor 1'}))
        
        service = SystemHealthService(hass)
        result = service._get_zigbee_health()
        
        # With 10 devices and 1 unavailable (10%), status should be healthy
        assert result['status'] == 'healthy'
        assert result['device_count'] == 10
        assert result['unavailable_devices'] == 1
    
    def test_get_zigbee_health_degraded(self):
        """Test Zigbee health when >10% devices unavailable."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        
        # Add coordinator
        hass.states.add(MockState('zha.device', 'online', {'friendly_name': 'Coordinator'}))
        hass.states.add(MockState('zha.network', 'online'))
        
        # Add 10 devices, 2 unavailable (20% - degraded)
        for i in range(10):
            state = 'online' if i < 8 else 'unavailable'
            hass.states.add(MockState(f'zha.device_{i}', state, {'friendly_name': f'Device {i}'}))
        
        service = SystemHealthService(hass)
        result = service._get_zigbee_health()
        
        assert result['status'] == 'degraded'
        assert result['device_count'] == 10
        assert result['unavailable_devices'] == 2
    
    def test_get_zwave_health_no_zwave(self):
        """Test Z-Wave health when no Z-Wave integration exists."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        result = service._get_zwave_health()
        
        assert result['status'] == 'healthy'
        assert result['node_count'] == 0
        assert result['ready_nodes'] == 0
    
    def test_get_zwave_health_with_nodes(self):
        """Test Z-Wave health with nodes present."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        
        # Add mock Z-Wave entities - 4 nodes, all ready (100% ready = healthy)
        hass.states.add(MockState('zwave.network_state', 'ready'))
        hass.states.add(MockState('zwave.node_1', 'ready', {}))
        hass.states.add(MockState('zwave.node_2', 'ready', {}))
        hass.states.add(MockState('zwave.node_3', 'ready', {}))
        hass.states.add(MockState('zwave.node_4', 'sleeping', {}))
        
        service = SystemHealthService(hass)
        result = service._get_zwave_health()
        
        # With 4 nodes and 3 ready (75%), status should be degraded (<80% ready)
        assert result['status'] == 'degraded'
        assert result['node_count'] == 4
        assert result['ready_nodes'] == 3
        assert result['sleeping_nodes'] == 1
        assert result['ready_percentage'] == 75.0
    
    def test_get_recorder_health_no_recorder(self):
        """Test Recorder health when no recorder entity exists."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        result = service._get_recorder_health()
        
        assert result['status'] == 'healthy'
        assert result['recording'] == False
    
    def test_get_recorder_health_with_recorder(self):
        """Test Recorder health with recorder entity."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        hass.states.add(MockState('recorder', 'recording', {'database_size': 500 * 1024 * 1024}))  # 500 MB
        
        service = SystemHealthService(hass)
        result = service._get_recorder_health()
        
        assert result['status'] == 'healthy'
        assert result['recording'] == True
        # database_size is returned as raw bytes from attributes when recorder module not available
        assert result['database_size'] == 500 * 1024 * 1024
    
    def test_get_recorder_health_large_db(self):
        """Test Recorder health when database is large."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        hass.states.add(MockState('recorder', 'recording', {'database_size': 1500 * 1024 * 1024}))  # 1.5 GB
        
        service = SystemHealthService(hass)
        result = service._get_recorder_health()
        
        assert result['status'] == 'degraded'
        # database_size is returned as raw bytes from attributes
        assert result['database_size'] == 1500 * 1024 * 1024
    
    def test_get_update_availability_no_updates(self):
        """Test update availability when no updates exist."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        result = service._get_update_availability()
        
        assert result['pending_updates'] == 0
        assert result['any_available'] == False
    
    def test_get_update_availability_with_updates(self):
        """Test update availability when updates exist."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        
        # Add update entities
        hass.states.add(MockState('update.home_assistant_core_update', 'on', {
            'current_version': '2024.1.0',
            'latest_version': '2024.2.0'
        }))
        hass.states.add(MockState('update.home_assistant_operating_system_update', 'off', {
            'current_version': '12.0',
            'latest_version': '12.1'
        }))
        
        service = SystemHealthService(hass)
        result = service._get_update_availability()
        
        assert result['pending_updates'] == 1
        assert result['any_available'] == True
        assert 'core' in result['updates']
        assert result['updates']['core']['available'] == True
    
    def test_get_overall_status_healthy(self):
        """Test overall status when all subsystems are healthy."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        # Force cache values
        service._cache = {
            'zigbee': {'status': 'healthy'},
            'zwave': {'status': 'healthy'},
            'recorder': {'status': 'healthy'},
            'updates': {'pending_updates': 0},
            'last_update': 12345
        }
        
        result = service._get_overall_status()
        
        assert result == 'healthy'
    
    def test_get_overall_status_degraded(self):
        """Test overall status when one subsystem is degraded."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        # Force cache values
        service._cache = {
            'zigbee': {'status': 'healthy'},
            'zwave': {'status': 'healthy'},
            'recorder': {'status': 'degraded'},
            'updates': {'pending_updates': 0},
            'last_update': 12345
        }
        
        result = service._get_overall_status()
        
        assert result == 'degraded'
    
    def test_get_overall_status_unhealthy(self):
        """Test overall status when multiple subsystems have issues."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        # Force cache values
        service._cache = {
            'zigbee': {'status': 'unhealthy'},
            'zwave': {'status': 'healthy'},
            'recorder': {'status': 'healthy'},
            'updates': {'pending_updates': 2},
            'last_update': 12345
        }
        
        result = service._get_overall_status()
        
        assert result == 'unhealthy'
    
    def test_get_full_health(self):
        """Test full health snapshot retrieval."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        result = service.get_full_health()
        
        assert 'status' in result
        assert 'subsystems' in result
        assert 'zigbee' in result['subsystems']
        assert 'zwave' in result['subsystems']
        assert 'recorder' in result['subsystems']
        assert 'updates' in result['subsystems']
        assert 'timestamp' in result
        assert 'cache_ttl_seconds' in result
    
    def test_should_suppress_suggestions_healthy(self):
        """Test suggestion suppression when system is healthy."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        # Force healthy cache
        service._cache = {
            'zigbee': {'status': 'healthy'},
            'zwave': {'status': 'healthy'},
            'recorder': {'status': 'healthy'},
            'updates': {'pending_updates': 0},
            'last_update': 12345
        }
        
        result = service.should_suppress_suggestions()
        
        assert result['suppress'] == False
        assert result['overall_status'] == 'healthy'
        assert len(result['reasons']) == 0
    
    def test_should_suppress_suggestions_unhealthy(self):
        """Test suggestion suppression when system is unhealthy."""
        import time
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        # Force unhealthy cache with multiple issues (2+ issues = unhealthy)
        service._cache = {
            'zigbee': {'status': 'unhealthy'},
            'zwave': {'status': 'unhealthy'},  # Second issue
            'recorder': {'status': 'healthy'},
            'updates': {'pending_updates': 0},
            'last_update': time.time()  # Now = cache valid
        }
        
        result = service.should_suppress_suggestions()
        
        # 2+ issues = unhealthy status triggers suppression
        assert result['suppress'] == True
        assert result['overall_status'] == 'unhealthy'
        # Should have reasons mentioning subsystems
        assert len(result['reasons']) > 0
    
    def test_get_zone_specific_health(self):
        """Test getting specific subsystem health."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        hass.states.add(MockState('zha.device', 'online', {'friendly_name': 'Coordinator'}))
        hass.states.add(MockState('zha.network', 'online'))
        
        service = SystemHealthService(hass)
        
        zigbee = service.get_zigbee_health()
        assert zigbee['status'] == 'healthy'
        
        zwave = service.get_zwave_health()
        assert zwave['status'] == 'healthy'
        
        recorder = service.get_recorder_health()
        assert recorder['status'] == 'healthy'
        
        updates = service.get_update_status()
        assert updates['pending_updates'] == 0


class TestSystemHealthAPI:
    """Test SystemHealth Flask API routes."""
    
    def test_system_health_endpoint_no_service(self):
        """Test /api/v1/system_health when service not initialized."""
        from copilot_core.system_health.api import system_health_bp, _get_service
        from flask import Flask
        
        app = Flask(__name__)
        app.register_blueprint(system_health_bp)
        
        with app.test_client() as client:
            response = client.get('/api/v1/system_health')
            assert response.status_code in [503, 401]  # 401 if API key required, 503 if no service
    
    def test_module_import(self):
        """Test module can be imported."""
        from copilot_core.system_health import SystemHealthService, system_health_bp
        
        assert SystemHealthService is not None
        assert system_health_bp is not None
    
    def test_blueprint_has_expected_routes(self):
        """Test blueprint has expected route definitions."""
        from copilot_core.system_health.api import system_health_bp
        from flask import Flask
        
        # Need to register blueprint to an app to access routes
        app = Flask(__name__)
        app.register_blueprint(system_health_bp)
        
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        
        assert '/api/v1/system_health' in routes
        assert '/api/v1/system_health/zigbee' in routes
        assert '/api/v1/system_health/zwave' in routes
        assert '/api/v1/system_health/recorder' in routes
        assert '/api/v1/system_health/updates' in routes
        assert '/api/v1/system_health/suppress' in routes


class TestSystemHealthCache:
    """Test SystemHealth caching behavior."""
    
    def test_cache_invalidation(self):
        """Test cache can be invalidated."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        # Get initial health to populate cache
        service.get_full_health()
        
        # Verify cache is populated
        assert service._cache['zigbee'] is not None
        
        # Invalidate cache
        service._invalidate_cache()
        
        # Verify cache is cleared
        assert service._cache['zigbee'] is None
        assert service._cache['last_update'] is None
    
    def test_force_refresh(self):
        """Test force refresh parameter."""
        from copilot_core.system_health.service import SystemHealthService
        
        hass = MockHass()
        service = SystemHealthService(hass)
        
        # Get initial health
        service.get_full_health()
        initial_timestamp = service._cache['last_update']
        
        # Force refresh should get new data
        result = service.get_full_health(force_refresh=True)
        
        assert result is not None
        assert 'status' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
