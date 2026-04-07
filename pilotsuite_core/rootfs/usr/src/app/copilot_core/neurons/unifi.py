"""UniFi Context Neuron - Network status for context-aware suggestions.

Evaluates UniFi network status for:
- WAN quality (latency, packet loss)
- Client roaming patterns (presence context)
- Traffic anomalies (energy-saving opportunities)

Output: 0.0 (network issues) to 1.0 (optimal network)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from enum import Enum

from .base import ContextNeuron, NeuronConfig, NeuronType

_LOGGER = logging.getLogger(__name__)


class NetworkQuality(str, Enum):
    """Network quality categories."""
    EXCELLENT = "excellent"  # <10ms latency, 0% loss
    GOOD = "good"            # <50ms latency, <1% loss
    FAIR = "fair"            # <100ms latency, <3% loss
    POOR = "poor"            # >100ms latency or >3% loss
    OFFLINE = "offline"      # No connection


class UniFiContextNeuron(ContextNeuron):
    """Evaluates UniFi network status for context-aware suggestions.
    
    Inputs:
        - WAN online status
        - WAN latency (ms)
        - Packet loss percentage
        - Client roaming events (optional)
    
    Output: 0.0 (poor/offline) to 1.0 (excellent)
    
    Factors:
        - WAN quality affects all automations
        - High latency = avoid streaming/sync suggestions
        - Offline = suppress non-critical suggestions
    """
    
    def __init__(self, config: NeuronConfig):
        """Initialize UniFi context neuron."""
        super().__init__(config, NeuronType.CONTEXT)
        
        # Entity configuration
        self.wan_entity: Optional[str] = config.extra.get("wan_entity")
        self.latency_entity: Optional[str] = config.extra.get("latency_entity")
        self.packet_loss_entity: Optional[str] = config.extra.get("packet_loss_entity")
        
        # Thresholds
        self.latency_warning_ms: float = config.extra.get("latency_warning_ms", 50.0)
        self.latency_critical_ms: float = config.extra.get("latency_critical_ms", 100.0)
        self.loss_warning_percent: float = config.extra.get("loss_warning_percent", 1.0)
        self.loss_critical_percent: float = config.extra.get("loss_critical_percent", 3.0)
        
        # State
        self._quality: NetworkQuality = NetworkQuality.GOOD
        self._latency: float = 0.0
        self._packet_loss: float = 0.0
        self._online: bool = True
    
    @classmethod
    def from_config(cls, config: NeuronConfig) -> "UniFiContextNeuron":
        """Create neuron from config."""
        return cls(config)
    
    def evaluate(self, context: Dict[str, Any]) -> float:
        """Evaluate network quality.
        
        Returns:
            Network quality score (0.0 - 1.0)
        """
        ha_states = context.get("ha_states", {})
        
        # Check WAN status
        if self.wan_entity:
            state = ha_states.get(self.wan_entity)
            if state:
                self._online = state.state.lower() in ("online", "on", "connected")
        
        # Offline = 0 score
        if not self._online:
            self._quality = NetworkQuality.OFFLINE
            self._state.value = 0.0
            self._state.confidence = 1.0
            return 0.0
        
        # Get latency
        if self.latency_entity:
            state = ha_states.get(self.latency_entity)
            if state:
                try:
                    self._latency = float(state.state)
                except (ValueError, TypeError):
                    pass
        
        # Get packet loss
        if self.packet_loss_entity:
            state = ha_states.get(self.packet_loss_entity)
            if state:
                try:
                    self._packet_loss = float(state.state)
                except (ValueError, TypeError):
                    pass
        
        # Calculate quality score
        score = self._calculate_quality_score()
        
        self._state.value = score
        self._state.confidence = 0.9 if self._online else 1.0
        self._state.last_update = datetime.now(timezone.utc).isoformat()
        
        return score
    
    def _calculate_quality_score(self) -> float:
        """Calculate overall network quality score."""
        # Latency score (0-1, lower is better)
        if self._latency < 10:
            latency_score = 1.0
            self._quality = NetworkQuality.EXCELLENT
        elif self._latency < self.latency_warning_ms:
            latency_score = 0.9
            self._quality = NetworkQuality.GOOD
        elif self._latency < self.latency_critical_ms:
            latency_score = 0.6
            self._quality = NetworkQuality.FAIR
        else:
            latency_score = 0.3
            self._quality = NetworkQuality.POOR
        
        # Packet loss score (0-1, lower is better)
        if self._packet_loss == 0:
            loss_score = 1.0
        elif self._packet_loss < self.loss_warning_percent:
            loss_score = 0.9
        elif self._packet_loss < self.loss_critical_percent:
            loss_score = 0.6
        else:
            loss_score = 0.3
            self._quality = NetworkQuality.POOR
        
        # Combined score (weighted average)
        # Latency is more important for real-time apps
        score = (latency_score * 0.6) + (loss_score * 0.4)
        
        return max(0.0, min(1.0, score))
    
    def get_quality(self) -> NetworkQuality:
        """Get current network quality category."""
        return self._quality
    
    def get_diagnostic_info(self) -> Dict[str, Any]:
        """Get diagnostic information."""
        return {
            "quality": self._quality.value,
            "online": self._online,
            "latency_ms": self._latency,
            "packet_loss_percent": self._packet_loss,
            "score": self._state.value,
            "confidence": self._state.confidence,
        }
    
    def get_suggestions_suppression(self) -> Dict[str, Any]:
        """Get suggestion suppression info.
        
        Returns suppression recommendations based on network quality.
        """
        suppress = []
        reasons = []
        
        if not self._online:
            suppress.extend(["streaming", "sync", "backup", "large_downloads"])
            reasons.append("Network offline")
        elif self._quality == NetworkQuality.POOR:
            suppress.extend(["streaming", "large_downloads"])
            reasons.append(f"High latency ({self._latency:.0f}ms) or packet loss ({self._packet_loss:.1f}%)")
        elif self._quality == NetworkQuality.FAIR:
            suppress.append("large_downloads")
            reasons.append(f"Moderate network issues (latency: {self._latency:.0f}ms)")
        
        return {
            "suppress": suppress,
            "reasons": reasons,
            "quality": self._quality.value,
        }


# Factory function
def create_unifi_context_neuron(
    wan_entity: Optional[str] = None,
    latency_entity: Optional[str] = None,
    packet_loss_entity: Optional[str] = None,
    latency_warning_ms: float = 50.0,
    latency_critical_ms: float = 100.0,
    loss_warning_percent: float = 1.0,
    loss_critical_percent: float = 3.0,
    name: str = "UniFi Network",
) -> UniFiContextNeuron:
    """Create UniFi context neuron."""
    config = NeuronConfig(
        id="unifi_context",
        name=name,
        extra={
            "wan_entity": wan_entity,
            "latency_entity": latency_entity,
            "packet_loss_entity": packet_loss_entity,
            "latency_warning_ms": latency_warning_ms,
            "latency_critical_ms": latency_critical_ms,
            "loss_warning_percent": loss_warning_percent,
            "loss_critical_percent": loss_critical_percent,
        },
    )
    return UniFiContextNeuron(config)


# Export
UNIFI_NEURON_CLASSES = {
    "unifi_context": UniFiContextNeuron,
}

__all__ = [
    "UniFiContextNeuron",
    "NetworkQuality",
    "create_unifi_context_neuron",
    "UNIFI_NEURON_CLASSES",
]