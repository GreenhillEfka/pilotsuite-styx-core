"""
UniFi Neuron - Network Monitoring Module

Provides WAN status, client roaming, and traffic baselines
for PilotSuite context awareness.
"""

__version__ = "0.1.0"

from .service import UniFiService

__all__ = ["UniFiService"]
