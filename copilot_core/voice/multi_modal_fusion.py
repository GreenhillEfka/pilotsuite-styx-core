"""Multi-Modal Fusion — Combining Voice, Visual, and Sensor Context."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import time

logger = logging.getLogger(__name__)


class Modality(Enum):
    """Input modalities."""
    VOICE = "voice"
    VISUAL = "visual"
    SENSOR = "sensor"
    LOCATION = "location"
    TEMPORAL = "temporal"


@dataclass
class ModalInput:
    """Input from a specific modality."""
    modality: Modality
    data: Dict[str, Any]
    confidence: float
    timestamp: float = field(default_factory=lambda: time.time())


@dataclass
class FusedContext:
    """Fused multi-modal context."""
    intent: str
    entities: List[Dict]
    confidence: float
    modalities: List[Modality]
    summary: str
    timestamp: float = field(default_factory=lambda: time.time())


class MultiModalFusionEngine:
    """Fuses multiple input modalities to understand rich context."""

    def __init__(self):
        self._recent_inputs: List[ModalInput] = []
        self._fusion_history: List[FusedContext] = []
        self._modality_weights: Dict[Modality, float] = {
            Modality.VOICE: 0.6,
            Modality.VISUAL: 0.2,
            Modality.SENSOR: 0.1,
            Modality.LOCATION: 0.05,
            Modality.TEMPORAL: 0.05,
        }

    def add_input(self, modal_input: ModalInput):
        """Add input from a modality."""
        self._recent_inputs.append(modal_input)
        
        # Keep only last 10 seconds of input for fusion
        cutoff = time.time() - 10.0
        self._recent_inputs = [i for i in self._recent_inputs if i.timestamp >= cutoff]
        
        logger.info(f"Added input: {modal_input.modality.value} (conf: {modal_input.confidence:.2f})")

    def fuse_context(self) -> FusedContext:
        """Fuse recent inputs into a single context."""
        if not self._recent_inputs:
            return FusedContext("none", [], 0.0, [], "No active context")
            
        # Group inputs by modality
        by_modality = {}
        for inp in self._recent_inputs:
            if inp.modality not in by_modality:
                by_modality[inp.modality] = []
            by_modality[inp.modality].append(inp)
            
        # Determine primary intent
        # In production, would use cross-modal transformer
        voice_intent = self._extract_voice_intent(by_modality.get(Modality.VOICE, []))
        visual_intent = self._extract_visual_intent(by_modality.get(Modality.VISUAL, []))
        
        # Fuse intent
        if voice_intent and visual_intent:
            intent = voice_intent
            confidence = 0.9
        else:
            intent = voice_intent or visual_intent or "unknown"
            confidence = 0.7
            
        context = FusedContext(
            intent=intent,
            entities=self._fuse_entities(by_modality),
            confidence=confidence,
            modalities=list(by_modality.keys()),
            summary=f"Fused context from {len(by_modality)} modalities"
        )
        
        self._fusion_history.append(context)
        return context

    def _extract_voice_intent(self, inputs: List[ModalInput]) -> Optional[str]:
        """Extract intent from voice inputs."""
        if not inputs: return None
        return inputs[0].data.get("intent")

    def _extract_visual_intent(self, inputs: List[ModalInput]) -> Optional[str]:
        """Extract intent from visual inputs."""
        if not inputs: return None
        return inputs[0].data.get("detected_action")

    def _fuse_entities(self, by_modality: Dict[Modality, List[ModalInput]]) -> List[Dict]:
        """Fuse entities from all modalities."""
        entities = []
        seen = set()
        
        for modality, inputs in by_modality.items():
            for inp in inputs:
                for ent in inp.data.get("entities", []):
                    key = f"{ent.get('type')}:{ent.get('value')}"
                    if key not in seen:
                        entities.append(ent)
                        seen.add(key)
        
        return entities

    def get_stats(self) -> Dict[str, Any]:
        """Get fusion statistics."""
        return {
            "recent_inputs": len(self._recent_inputs),
            "fusion_count": len(self._fusion_history),
            "active_modalities": list(set(i.modality.value for i in self._recent_inputs)),
        }


# Global default fusion engine
default_multi_modal: Optional[MultiModalFusionEngine] = None


def init_multi_modal_fusion() -> MultiModalFusionEngine:
    """Initialize global multi-modal fusion engine."""
    global default_multi_modal
    default_multi_modal = MultiModalFusionEngine()
    return default_multi_modal
