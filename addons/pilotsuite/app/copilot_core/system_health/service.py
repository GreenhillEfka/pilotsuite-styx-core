"""
SystemHealth Neuron - Monitor Zigbee/Z-Wave Mesh, Recorder, and system updates.

Provides health diagnostics for Home Assistant subsystems that influence
automation quality and suggestion relevance.
"""

import logging

logger = logging.getLogger(__name__)


class SystemHealthService:
    """
    Service for monitoring Home Assistant system health metrics.
    
    Provides diagnostics for:
    - Zigbee mesh stability (pairing, network health)
    - Z-Wave mesh status (nodes, network status)
    - Recorder statistics (database size, retention)
    - HA update availability (Core, OS, Supervised)
    """
    
    def __init__(self, hass):
        """
        Initialize SystemHealth service.
        
        Args:
            hass: Home Assistant hass object for registry access
        """
        self.hass = hass
        self._cache = {
            'zigbee': None,
            'zwave': None,
            'recorder': None,
            'updates': None,
            'last_update': None
        }
        self._cache_ttl = 300  # 5 minutes
    
    def _is_cache_valid(self):
        """Check if cache is still valid."""
        import time
        if self._cache['last_update'] is None:
            return False
        return (time.time() - self._cache['last_update']) < self._cache_ttl
    
    def _invalidate_cache(self):
        """Clear the cache to force refresh."""
        self._cache = {
            'zigbee': None,
            'zwave': None,
            'recorder': None,
            'updates': None,
            'last_update': None
        }
    
    def _update_cache(self):
        """Refresh all cached metrics."""
        import time
        self._cache['zigbee'] = self._get_zigbee_health()
        self._cache['zwave'] = self._get_zwave_health()
        self._cache['recorder'] = self._get_recorder_health()
        self._cache['updates'] = self._get_update_availability()
        self._cache['last_update'] = time.time()
    
    def get_full_health(self, force_refresh=False):
        """
        Get complete system health snapshot.
        
        Args:
            force_refresh: Ignore cache and fetch fresh data
            
        Returns:
            dict: Complete health status for all subsystems
        """
        if force_refresh or not self._is_cache_valid():
            self._update_cache()
        
        return {
            'status': self._get_overall_status(),
            'subsystems': {
                'zigbee': self._cache['zigbee'],
                'zwave': self._cache['zwave'],
                'recorder': self._cache['recorder'],
                'updates': self._cache['updates']
            },
            'timestamp': self._cache['last_update'],
            'cache_ttl_seconds': self._cache_ttl
        }
    
    def _get_overall_status(self):
        """Calculate overall system health status."""
        issues = []
        
        # Check each subsystem for issues
        if self._cache['zigbee'] and self._cache['zigbee'].get('status') != 'healthy':
            issues.append('zigbee')
        
        if self._cache['zwave'] and self._cache['zwave'].get('status') != 'healthy':
            issues.append('zwave')
        
        if self._cache['recorder'] and self._cache['recorder'].get('status') != 'healthy':
            issues.append('recorder')
        
        if self._cache['updates'] and self._cache['updates'].get('pending_updates', 0) > 0:
            issues.append('updates')
        
        if not issues:
            return 'healthy'
        elif len(issues) == 1:
            return 'degraded'
        else:
            return 'unhealthy'
    
    def _get_zigbee_health(self):
        """
        Get Zigbee mesh health metrics.
        
        Checks:
        - ZHA integration state
        - Network state (coordinator online)
        - Device count and pending queries
        """
        try:
            # Check ZHA integration
            zha_entities = [
                entity for entity in self.hass.states.async_all()
                if entity.entity_id.startswith('zha.') or 
                   (entity.domain == 'sensor' and 'zigbee' in entity.entity_id.lower())
            ]
            
            # Look for coordinator
            coordinator = None
            network_form = None
            device_count = 0
            
            for state in self.hass.states.async_all():
                if state.entity_id == 'zha.device':
                    coordinator = state
                elif state.entity_id == 'zha.network':
                    network_form = state
                elif state.entity_id.startswith('zha.') and '.device_' in state.entity_id:
                    device_count += 1
            
            # Check for problematic devices
            problem_devices = []
            for state in self.hass.states.async_all():
                if state.entity_id.startswith('zha.') and state.state == 'unavailable':
                    problem_devices.append({
                        'entity_id': state.entity_id,
                        'friendly_name': state.attributes.get('friendly_name', 'Unknown')
                    })
            
            status = 'healthy'
            if coordinator and coordinator.state != 'online':
                status = 'unhealthy'
            elif len(problem_devices) > 0 and len(problem_devices) > device_count * 0.1:
                status = 'degraded'  # >10% devices unavailable
            
            return {
                'status': status,
                'coordinator_online': coordinator.state == 'online' if coordinator else False,
                'device_count': device_count,
                'unavailable_devices': len(problem_devices),
                'problem_details': problem_devices[:5] if problem_devices else [],  # Max 5
                'network_form': network_form.state if network_form else None
            }
            
        except Exception as e:
            logger.warning(f"Error getting Zigbee health: {e}")
            return {
                'status': 'unknown',
                'error': str(e)
            }
    
    def _get_zwave_health(self):
        """
        Get Z-Wave mesh health metrics.
        
        Checks:
        - Z-Wave JS integration state
        - Network state
        - Node count and ready status
        """
        try:
            # Look for Z-Wave JS entities
            zwave_entities = [
                entity for entity in self.hass.states.async_all()
                if 'zwave' in entity.entity_id.lower() or 'z-wave' in entity.entity_id.lower()
            ]
            
            # Check network state
            network_state = None
            ready_count = 0
            total_count = 0
            sleeping_count = 0
            
            for state in self.hass.states.async_all():
                if 'zwave' in state.entity_id.lower():
                    if 'network' in state.entity_id and 'state' in state.entity_id:
                        network_state = state
                    if '.node_' in state.entity_id:
                        total_count += 1
                        if state.state == 'ready':
                            ready_count += 1
                        elif state.state == 'sleeping':
                            sleeping_count += 1
            
            status = 'healthy'
            if network_state:
                if network_state.state == 'offline':
                    status = 'unhealthy'
                elif network_state.state == 'dead':
                    status = 'unhealthy'
                elif ready_count < total_count * 0.8:  # <80% ready
                    status = 'degraded'
            
            return {
                'status': status,
                'network_state': network_state.state if network_state else None,
                'node_count': total_count,
                'ready_nodes': ready_count,
                'sleeping_nodes': sleeping_count,
                'ready_percentage': round(ready_count / total_count * 100, 1) if total_count > 0 else 0
            }
            
        except Exception as e:
            logger.warning(f"Error getting Z-Wave health: {e}")
            return {
                'status': 'unknown',
                'error': str(e)
            }
    
    def _get_recorder_health(self):
        """
        Get Recorder database health metrics.
        
        Checks:
        - Database size
        - Recording state
        - Oldest/newest recording timestamps
        """
        try:
            # Check recorder entity
            recorder_state = None
            db_size = None
            recording = False
            
            for state in self.hass.states.async_all():
                if state.entity_id == 'recorder':
                    recorder_state = state
                    db_size = state.attributes.get('database_size')
                    recording = state.state == 'recording'
                    break
            
            # Get statistics from recorder history
            # Note: This requires access to recorder statistics, may be limited
            stats = {}
            try:
                from homeassistant.helpers import recorder
                if recorder.is_instance(self.hass):
                    db_path = recorder.get_instance(self.hass).database_path
                    import os
                    if os.path.exists(db_path):
                        db_size_bytes = os.path.getsize(db_path)
                        stats['size_bytes'] = db_size_bytes
                        stats['size_mb'] = round(db_size_bytes / (1024 * 1024), 2)
            except Exception:
                pass
            
            status = 'healthy'
            if db_size and isinstance(db_size, (int, float)):
                size_mb = db_size / (1024 * 1024) if db_size > 1024 else db_size
                if size_mb > 1000:  # >1GB
                    status = 'degraded'
                elif size_mb > 2000:  # >2GB
                    status = 'unhealthy'
            
            return {
                'status': status,
                'database_size': stats.get('size_mb', db_size),
                'database_size_bytes': stats.get('size_bytes'),
                'recording': recording,
                'recorder_state': recorder_state.state if recorder_state else None
            }
            
        except Exception as e:
            logger.warning(f"Error getting recorder health: {e}")
            return {
                'status': 'unknown',
                'error': str(e)
            }
    
    def _get_update_availability(self):
        """
        Get Home Assistant update availability.
        
        Returns:
            dict: Available updates for Core, OS, Supervised
        """
        try:
            updates = {}
            
            # Check for updates
            for state in self.hass.states.async_all():
                if 'update' in state.entity_id:
                    entity_id = state.entity_id
                    if 'home_assistant_core' in entity_id or 'core' in entity_id:
                        updates['core'] = {
                            'entity_id': entity_id,
                            'current_version': state.attributes.get('current_version'),
                            'latest_version': state.attributes.get('latest_version'),
                            'available': state.state != 'off',
                            'skipped': state.attributes.get('skipped_version') is not None
                        }
                    elif 'home_assistant_operating_system' in entity_id or 'os' in entity_id:
                        updates['os'] = {
                            'entity_id': entity_id,
                            'current_version': state.attributes.get('current_version'),
                            'latest_version': state.attributes.get('latest_version'),
                            'available': state.state != 'off'
                        }
                    elif 'home_assistant_supervised' in entity_id or 'supervised' in entity_id:
                        updates['supervised'] = {
                            'entity_id': entity_id,
                            'current_version': state.attributes.get('current_version'),
                            'latest_version': state.attributes.get('latest_version'),
                            'available': state.state != 'off'
                        }
            
            pending_updates = sum(1 for u in updates.values() if u.get('available'))
            
            return {
                'pending_updates': pending_updates,
                'updates': updates,
                'any_available': pending_updates > 0
            }
            
        except Exception as e:
            logger.warning(f"Error getting update availability: {e}")
            return {
                'status': 'unknown',
                'error': str(e)
            }
    
    def get_zigbee_health(self, force_refresh=False):
        """Get Zigbee health specifically."""
        if force_refresh or not self._is_cache_valid():
            self._update_cache()
        return self._cache['zigbee']
    
    def get_zwave_health(self, force_refresh=False):
        """Get Z-Wave health specifically."""
        if force_refresh or not self._is_cache_valid():
            self._update_cache()
        return self._cache['zwave']
    
    def get_recorder_health(self, force_refresh=False):
        """Get Recorder health specifically."""
        if force_refresh or not self._is_cache_valid():
            self._update_cache()
        return self._cache['recorder']
    
    def get_update_status(self, force_refresh=False):
        """Get update availability specifically."""
        if force_refresh or not self._is_cache_valid():
            self._update_cache()
        return self._cache['updates']
    
    def should_suppress_suggestions(self):
        """
        Determine if we should suppress automation suggestions.
        
        Returns:
            dict: Suppression info with reason
        """
        health = self.get_full_health()
        
        reasons = []
        
        if health['status'] == 'unhealthy':
            reasons.append('System health is unhealthy')
            subs = health.get('subsystems', {})
            for sub, data in subs.items():
                if data.get('status') == 'unhealthy':
                    reasons.append(f'{sub} subsystem is unhealthy')
        
        if health['status'] == 'degraded':
            subs = health.get('subsystems', {})
            for sub, data in subs.items():
                if data.get('status') == 'degraded':
                    reasons.append(f'{sub} subsystem is degraded')
        
        return {
            'suppress': health['status'] in ['unhealthy', 'degraded'],
            'reasons': reasons,
            'overall_status': health['status']
        }
