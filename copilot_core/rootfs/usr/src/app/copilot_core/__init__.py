"""
PilotSuite Core Package

Core services for PilotSuite:
- Brain Graph: Event processing and pattern detection
- Candidates: Automation suggestion storage
- Habitus: A→B pattern mining
- Mood: Context-aware suggestion weighting
- SystemHealth: Zigbee/Z-Wave/Recorder monitoring
- UniFi: Network monitoring (WAN, clients, roaming)
- Dev Surface: Development utilities
"""

from .versioning import get_runtime_version

__version__ = get_runtime_version()

# Global service instances (initialized by init_services)
_system_health_service = None
_unifi_service = None
_brain_graph_service = None
_graph_renderer = None
_candidate_store = None
_habitus_service = None
_mood_service = None
_event_processor = None


def set_system_health_service(service):
    """Set the global SystemHealth service instance."""
    global _system_health_service
    _system_health_service = service


def get_system_health_service():
    """Get the global SystemHealth service instance."""
    return _system_health_service


def set_unifi_service(service):
    """Set the global UniFi service instance."""
    global _unifi_service
    _unifi_service = service


def get_unifi_service():
    """Get the global UniFi service instance."""
    return _unifi_service
