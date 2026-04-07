"""End-to-End Wiring — Verkabelt ALLE Komponenten für maximale Synergien.

Diese Komponente verbindet:
- AutoDiscovery → UnifiedHabitusStore
- UnifiedHabitusStore → Neurons
- Neurons → Anomaly Detection
- Anomaly Detection → HabitusService
- HabitusService → Chat API
- Chat API → User Feedback
- User Feedback → UnifiedHabitusStore (Confidence Update)
- Module Dependencies → Cross-Module Effects

Usage:
    wiring = get_end_to_end_wiring()
    wiring.start()  # Start event processing
    
    # Bei jedem HA-Event:
    wiring.on_ha_event(event)
    
    # Im Hintergrund:
    # - Event → Pattern → Store → Neurons → Anomaly → Chat → Feedback → Confidence
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import threading
import time

_LOGGER = logging.getLogger(__name__)


class EndToEndWiring:
    """Verkabelt alle Komponenten für End-to-End Learning.
    
    Flow:
    1. HA Event (state_changed)
    2. AutoDiscovery erkennt Pattern
    3. UnifiedHabitusStore speichert Record
    4. Neurons updaten Kontext/Stimmung
    5. Anomaly Detection prüft Abweichungen
    6. HabitusService generiert Vorschläge
    7. Chat API benachrichtigt Nutzer
    8. User Feedback (accept/reject/correct)
    9. UnifiedHabitusStore updatet Confidence
    10. Module Dependencies prüfen Cross-Module Effects
    """
    
    def __init__(self):
        self._store = None
        self._service = None
        self._neurons = None
        self._anomaly = None
        self._chat = None
        self._running = False
        self._event_queue: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        
        _LOGGER.info("EndToEndWiring initialized (lazy-load components)")
    
    def _lazy_init(self) -> None:
        """Lazy component initialization."""
        if self._store is None:
            from copilot_core.habitus.unified_habitus_store import get_unified_habitus_store
            self._store = get_unified_habitus_store()
        
        if self._service is None:
            from copilot_core.habitus.habitus_service import get_habitus_service
            self._service = get_habitus_service()
        
        if self._neurons is None:
            try:
                from copilot_core.neurons.manager import NeuronManager
                self._neurons = NeuronManager()
            except Exception as e:
                _LOGGER.warning(f"Neurons not available: {e}")
                self._neurons = None
        
        if self._anomaly is None:
            try:
                from copilot_core.anomaly.anomaly_detector import AnomalyDetector
                self._anomaly = AnomalyDetector()
            except Exception as e:
                _LOGGER.warning(f"Anomaly not available: {e}")
                self._anomaly = None
        
        if self._chat is None:
            try:
                from copilot_core.styx.chat_handler import ChatHandler
                self._chat = ChatHandler()
            except Exception as e:
                _LOGGER.warning(f"Chat not available: {e}")
                self._chat = None
    
    def start(self) -> None:
        """Start event processing."""
        self._running = True
        self._lazy_init()
        _LOGGER.info("EndToEndWiring started")
    
    def stop(self) -> None:
        """Stop event processing."""
        self._running = False
        _LOGGER.info("EndToEndWiring stopped")
    
    def on_ha_event(self, event: Dict[str, Any]) -> None:
        """HA-Event verarbeiten (End-to-End Flow).
        
        Args:
            event: HA state_changed Event
                {
                    "event_type": "state_changed",
                    "entity_id": "light.wohnzimmer",
                    "old_state": "off",
                    "new_state": "on",
                    "timestamp": "2026-04-01T19:30:00Z",
                    "context": {
                        "zone": "living",
                        "presence": True,
                        "time_of_day": "evening",
                    }
                }
        """
        with self._lock:
            self._event_queue.append(event)
            
            # Queue begrenzen (max 100 Events)
            if len(self._event_queue) > 100:
                self._event_queue = self._event_queue[-100:]
        
        # Event verarbeiten (kann async sein)
        threading.Thread(target=self._process_event, args=(event,), daemon=True).start()
    
    def _process_event(self, event: Dict[str, Any]) -> None:
        """Einzelnes Event verarbeiten (End-to-End Flow)."""
        try:
            zone = event.get("context", {}).get("zone")
            module = event.get("entity_id", "").split(".")[0]
            entity_id = event.get("entity_id", "")
            
            _LOGGER.debug(f"Processing event: {entity_id} in zone={zone}")
            
            # 1. AutoDiscovery: Pattern beobachten
            if self._service:
                pattern_id = self._service.observe(
                    trigger={
                        "time": event.get("timestamp", "")[:16].split("T")[1][:5] if "T" in event.get("timestamp", "") else "",
                        "presence": event.get("context", {}).get("presence"),
                        "zone": zone,
                    },
                    action={
                        "module": module,
                        "entity_id": entity_id,
                        "command": "turn_on" if event.get("new_state") in ("on", "true", "True") else "turn_off",
                    },
                    zone=zone,
                    module=module,
                )
                _LOGGER.debug(f"Pattern observed: {pattern_id}")
            
            # 2. UnifiedHabitusStore: Record speichern
            if self._store:
                from copilot_core.habitus.unified_habitus_store import UnifiedRecord, DataType
                
                record = UnifiedRecord(
                    id=f"event_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{entity_id}",
                    data_type=DataType.EVENT,
                    zone=zone,
                    module=module,
                    content=f"{entity_id} → {event.get('new_state')} at {event.get('timestamp', '')}",
                    title=f"{module} event in {zone}",
                    metadata=event,
                    tags=[zone, module] if zone and module else [],
                )
                self._store.save_record(record)
                _LOGGER.debug(f"Event saved to UnifiedHabitusStore")
            
            # 3. Neurons: Kontext updaten
            if self._neurons:
                try:
                    self._neurons.update_states({
                        entity_id: event.get("new_state"),
                    })
                    _LOGGER.debug("Neurons updated")
                except Exception as e:
                    _LOGGER.warning(f"Neuron update failed: {e}")
            
            # 4. Anomaly Detection: Prüfen ob anomal
            if self._anomaly and zone and module:
                try:
                    baseline_data = self._store.get_anomaly_baseline(zone, module)
                    if baseline_data:
                        is_anomaly = self._anomaly.detect(event, baseline_data["baseline"])
                        
                        if is_anomaly:
                            _LOGGER.warning(f"Anomaly detected in {zone}/{module}")
                            
                            # 5. User benachrichtigen via Chat
                            if self._chat:
                                try:
                                    self._chat.chat(
                                        query=f"Ungewöhnliches Verhalten erkannt in {zone}: {entity_id} → {event.get('new_state')}",
                                        session_id=f"anomaly_{zone}",
                                        context={"zone": zone, "anomaly": True},
                                    )
                                except Exception as e:
                                    _LOGGER.warning(f"Chat notification failed: {e}")
                except Exception as e:
                    _LOGGER.warning(f"Anomaly detection failed: {e}")
            
            # 6. Module Dependencies: Cross-Module Effects prüfen
            if self._store and module and zone:
                try:
                    deps = self._store.get_module_dependencies(module, zone)
                    
                    for dep in deps:
                        target_module = dep["target_module"]
                        dep_type = dep["dependency_type"]
                        strength = dep["strength"]
                        
                        if dep_type == "requires":
                            # Target-Module muss auch aktiv sein
                            _LOGGER.debug(f"Dependency: {module} requires {target_module} (strength: {strength})")
                            
                        elif dep_type == "enhances":
                            # Target-Module kann synergistisch genutzt werden
                            _LOGGER.debug(f"Dependency: {module} enhances {target_module} (strength: {strength})")
                            
                        elif dep_type == "conflicts":
                            # Target-Module sollte deaktiviert sein
                            _LOGGER.warning(f"Dependency conflict: {module} conflicts with {target_module}")
                except Exception as e:
                    _LOGGER.warning(f"Dependency check failed: {e}")
            
            # 7. HabitusService: Vorschläge generieren (wenn genug Support)
            if self._service and zone:
                try:
                    proposals = self._service.get_proposals(zone=zone, min_confidence=0.7, limit=3)
                    
                    if proposals:
                        _LOGGER.info(f"Generated {len(proposals)} proposals for zone {zone}")
                        
                        # Vorschläge via Chat senden
                        if self._chat:
                            for proposal in proposals[:1]:  # Nur top proposal
                                try:
                                    self._chat.chat(
                                        query=f"Soll ich das automatisch machen? {proposal['description']}",
                                        session_id=f"proposal_{zone}",
                                        context={"proposal": proposal, "zone": zone},
                                    )
                                except Exception as e:
                                    _LOGGER.warning(f"Proposal chat failed: {e}")
                except Exception as e:
                    _LOGGER.warning(f"Proposal generation failed: {e}")
            
            _LOGGER.debug(f"Event processing complete for {entity_id}")
            
        except Exception as e:
            _LOGGER.error(f"Event processing error: {e}", exc_info=True)
    
    def process_feedback(self, pattern_id: str, feedback_type: str, 
                         comment: Optional[str] = None,
                         correction: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Feedback verarbeiten (End-to-End).
        
        Args:
            pattern_id: Pattern-ID
            feedback_type: accepted, rejected, ignored, corrected
            comment: Optional Nutzer-Kommentar
            correction: Optional Korrektur-Vorschlag
        
        Returns:
            Result mit Confidence-Update
        """
        self._lazy_init()
        
        # 1. Feedback im Store speichern
        if self._store:
            from copilot_core.habitus.unified_habitus_store import UnifiedRecord, DataType
            
            feedback_record = UnifiedRecord(
                id=f"feedback_{pattern_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                data_type=DataType.PATTERN,  # Feedback ist Teil des Patterns
                content=f"Feedback: {feedback_type} for pattern {pattern_id}",
                title=f"Feedback: {feedback_type}",
                metadata={
                    "pattern_id": pattern_id,
                    "feedback_type": feedback_type,
                    "comment": comment,
                    "correction": correction,
                },
                tags=["feedback", feedback_type],
            )
            self._store.save_record(feedback_record)
        
        # 2. HabitusService: Confidence updaten
        if self._service:
            result = self._service.process_feedback(
                pattern_id=pattern_id,
                feedback_type=feedback_type,
                comment=comment,
                correction=correction,
            )
            
            # 3. Bei Correction: Module Dependencies updaten
            if correction and self._store:
                if "dependencies" in correction:
                    for dep in correction["dependencies"]:
                        self._store.save_module_dependency(
                            source_module=dep.get("source_module"),
                            target_module=dep.get("target_module"),
                            dependency_type=dep.get("type"),
                            strength=dep.get("strength", 0.5),
                        )
            
            return result
        
        return {"success": False, "error": "Service not available"}
    
    def get_end_to_end_stats(self) -> Dict[str, Any]:
        """Statistiken über End-to-End Flow."""
        self._lazy_init()
        
        stats = {
            "event_queue_size": len(self._event_queue),
            "running": self._running,
            "components": {
                "store": self._store is not None,
                "service": self._service is not None,
                "neurons": self._neurons is not None,
                "anomaly": self._anomaly is not None,
                "chat": self._chat is not None,
            },
        }
        
        if self._store:
            stats["unified_store"] = self._store.get_stats()
        
        return stats


# =============================================================================
# Singleton
# =============================================================================

_wiring_instance: Optional[EndToEndWiring] = None


def get_end_to_end_wiring() -> EndToEndWiring:
    """Singleton-Zugriff auf EndToEndWiring."""
    global _wiring_instance
    
    if _wiring_instance is None:
        _wiring_instance = EndToEndWiring()
        _wiring_instance.start()
    
    return _wiring_instance
