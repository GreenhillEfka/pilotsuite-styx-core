"""PilotSuite Sonos Integration — native Sonos-Steuerung via node-sonos-http-api."""

from copilot_core.sonos.client import SonosHTTPClient
from copilot_core.sonos.intelligence import SonosIntelligence

__all__ = ["SonosHTTPClient", "SonosIntelligence"]
