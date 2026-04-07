"""Auto-Discovery — Automatische Pattern-Erkennung aus Events.

Diese Komponente erkennt automatisch Patterns aus Event-Streams:
- Beobachtet HA-Events (state_changed)
- Erkennt wiederkehrende Muster (A→B)
- Schlägt neue Automatisierungen vor
- Lernt ohne explizite Konfiguration

Usage:
    discovery = AutoDiscovery()
    discovery.on_event(event)  # Bei jedem HA-Event aufrufen
    
    # Im Hintergrund:
    # - Events werden gesammelt (ContextHistory)
    # - Alle 60s: Pattern-Mining
    # - Bei stabilen Patterns: Vorschlag generieren
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import threading
import time

from .habitus_storage import (
    get_habitus_storage,
    HabitusStorage,
    Pattern,
    PatternState,
    ContextHistory,
)

_LOGGER = logging.getLogger(__name__)


class AutoDiscovery:
    """Automatische Pattern-Erkennung aus Event-Streams.
    
    Erkennt wiederkehrende Muster im Nutzerverhalten:
    - Zeit-basierte Muster (immer um 19:30)
    - Kontext-basierte Muster (wenn Präsenz + Abend)
    - Sequenz-basierte Muster (Licht an → Musik an → TV an)
    """
    
    def __init__(self, storage: Optional[HabitusStorage] = None):
        self._storage = storage or get_habitus_storage()
        self._event_buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._mining_interval = 60  # Alle 60s mining
        self._min_support = 5  # Mindestens 5 Wiederholungen
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        _LOGGER.info("AutoDiscovery initialized (interval=%ds, min_support=%d)", 
                     self._mining_interval, self._min_support)
    
    def start(self) -> None:
        """Background-Mining starten."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._mining_loop, daemon=True)
        self._thread.start()
        _LOGGER.info("AutoDiscovery started")
    
    def stop(self) -> None:
        """Background-Mining stoppen."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        _LOGGER.info("AutoDiscovery stopped")
    
    def _mining_loop(self) -> None:
        """Background-Mining Loop (alle 60s)."""
        while self._running:
            time.sleep(self._mining_interval)
            try:
                self._mine_patterns()
            except Exception as e:
                _LOGGER.error(f"Mining error: {e}")
    
    def on_event(self, event: Dict[str, Any]) -> None:
        """HA-Event verarbeiten.
        
        Args:
            event: HA state_changed Event
                {
                    "event_type": "state_changed",
                    "entity_id": "light.wohnzimmer",
                    "old_state": "off",
                    "new_state": "on",
                    "attributes": {...},
                    "timestamp": "2026-04-01T19:30:00Z",
                    "context": {
                        "zone": "living",
                        "presence": True,
                        "time": "19:30",
                    }
                }
        """
        with self._lock:
            self._event_buffer.append({
                **event,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            })
            
            # Buffer begrenzen (max 1000 Events)
            if len(self._event_buffer) > 1000:
                self._event_buffer = self._event_buffer[-1000:]
        
        # In ContextHistory speichern (für langfristiges Lernen)
        try:
            context = ContextHistory(
                timestamp=event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                zone=event.get("context", {}).get("zone", "unknown"),
                modules=[event.get("entity_id", "").split(".")[0]],
                entities={event.get("entity_id"): event.get("new_state")},
                mood=None,
                events=[event],
            )
            self._storage.add_context(context)
        except Exception as e:
            _LOGGER.warning(f"Could not save context: {e}")
    
    def _mine_patterns(self) -> None:
        """Pattern-Mining auf Event-Buffer."""
        with self._lock:
            events = self._event_buffer.copy()
        
        if len(events) < self._min_support:
            return  # Nicht genug Daten
        
        _LOGGER.info(f"Mining {len(events)} events for patterns...")
        
        # 1. Zeit-basierte Muster erkennen
        time_patterns = self._mine_time_patterns(events)
        
        # 2. Kontext-basierte Muster erkennen
        context_patterns = self._mine_context_patterns(events)
        
        # 3. Sequenz-basierte Muster erkennen
        sequence_patterns = self._mine_sequence_patterns(events)
        
        # Patterns speichern (wenn neu)
        all_patterns = time_patterns + context_patterns + sequence_patterns
        
        for pattern_data in all_patterns:
            self._save_or_update_pattern(pattern_data)
        
        _LOGGER.info(f"Mining complete: {len(all_patterns)} patterns found")
    
    def _mine_time_patterns(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Zeit-basierte Muster erkennen (immer um X Uhr)."""
        # Gruppieren nach Zeit (±15 Minuten Fenster)
        time_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        for event in events:
            timestamp = event.get("timestamp", "")
            if not timestamp:
                continue
            
            # Zeit extrahieren (HH:MM)
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_key = dt.strftime("%H:%M")
                # Auf 15-Minuten-Fenster runden
                minute = (dt.minute // 15) * 15
                time_key = f"{dt.hour:02d}:{minute:02d}"
            except Exception:
                continue
            
            time_groups[time_key].append(event)
        
        # Muster mit genug Support extrahieren
        patterns = []
        for time_key, group_events in time_groups.items():
            if len(group_events) < self._min_support:
                continue
            
            # Häufigste Aktion in dieser Zeit
            action_counts: Dict[str, int] = defaultdict(int)
            for e in group_events:
                entity_id = e.get("entity_id", "")
                new_state = e.get("new_state", "")
                action_key = f"{entity_id}:{new_state}"
                action_counts[action_key] += 1
            
            if not action_counts:
                continue
            
            top_action = max(action_counts.items(), key=lambda x: x[1])
            entity_id, state = top_action[0].rsplit(":", 1)
            
            patterns.append({
                "trigger": {
                    "time": time_key,
                },
                "action": {
                    "module": entity_id.split(".")[0],
                    "entity_id": entity_id,
                    "command": "turn_on" if state in ("on", "true", "True") else "turn_off",
                },
                "support": top_action[1],
                "description": f"Immer um {time_key}: {entity_id} → {state}",
            })
        
        return patterns
    
    def _mine_context_patterns(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Kontext-basierte Muster erkennen (wenn Präsenz + Abend)."""
        # Gruppieren nach Kontext
        context_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        for event in events:
            context = event.get("context", {})
            if not context:
                continue
            
            # Kontext-Key erstellen
            context_parts = []
            if context.get("presence"):
                context_parts.append("presence")
            if context.get("time_of_day"):
                context_parts.append(context["time_of_day"])
            if context.get("zone"):
                context_parts.append(context["zone"])
            
            if not context_parts:
                continue
            
            context_key = "|".join(sorted(context_parts))
            context_groups[context_key].append(event)
        
        # Muster mit genug Support extrahieren
        patterns = []
        for context_key, group_events in context_groups.items():
            if len(group_events) < self._min_support:
                continue
            
            # Häufigste Aktion in diesem Kontext
            action_counts: Dict[str, int] = defaultdict(int)
            for e in group_events:
                entity_id = e.get("entity_id", "")
                new_state = e.get("new_state", "")
                action_key = f"{entity_id}:{new_state}"
                action_counts[action_key] += 1
            
            if not action_counts:
                continue
            
            top_action = max(action_counts.items(), key=lambda x: x[1])
            entity_id, state = top_action[0].rsplit(":", 1)
            
            # Kontext parsen
            trigger = {}
            for part in context_key.split("|"):
                if part == "presence":
                    trigger["presence"] = True
                elif part in ("morning", "afternoon", "evening", "night"):
                    trigger["time_of_day"] = part
                else:
                    trigger["zone"] = part
            
            patterns.append({
                "trigger": trigger,
                "action": {
                    "module": entity_id.split(".")[0],
                    "entity_id": entity_id,
                    "command": "turn_on" if state in ("on", "true", "True") else "turn_off",
                },
                "support": top_action[1],
                "description": f"Wenn {context_key}: {entity_id} → {state}",
            })
        
        return patterns
    
    def _mine_sequence_patterns(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sequenz-basierte Muster erkennen (A → B → C)."""
        # Events nach Zeit sortieren
        sorted_events = sorted(
            events,
            key=lambda e: e.get("timestamp", ""),
        )
        
        # Sequenzen von 2-3 Events erkennen
        sequences: Dict[str, int] = defaultdict(int)
        
        for i in range(len(sorted_events) - 1):
            e1 = sorted_events[i]
            e2 = sorted_events[i + 1]
            
            # Zeit-Differenz prüfen (max 5 Minuten)
            try:
                t1 = datetime.fromisoformat(e1.get("timestamp", "").replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(e2.get("timestamp", "").replace("Z", "+00:00"))
                diff = (t2 - t1).total_seconds()
                
                if diff > 300:  # 5 Minuten
                    continue
            except Exception:
                continue
            
            # Sequenz-Key erstellen
            seq_key = f"{e1.get('entity_id')}:{e1.get('new_state')}→{e2.get('entity_id')}:{e2.get('new_state')}"
            sequences[seq_key] += 1
        
        # Sequenzen mit genug Support extrahieren
        patterns = []
        for seq_key, support in sequences.items():
            if support < self._min_support:
                continue
            
            # Sequenz parsen
            parts = seq_key.split("→")
            if len(parts) != 2:
                continue
            
            entity1, state1 = parts[0].rsplit(":", 1)
            entity2, state2 = parts[1].rsplit(":", 1)
            
            patterns.append({
                "trigger": {
                    "entity_id": entity1,
                    "state": state1,
                },
                "action": {
                    "module": entity2.split(".")[0],
                    "entity_id": entity2,
                    "command": "turn_on" if state2 in ("on", "true", "True") else "turn_off",
                },
                "support": support,
                "description": f"Wenn {entity1} → {state1}, dann {entity2} → {state2}",
                "sequence": True,
            })
        
        return patterns
    
    def _save_or_update_pattern(self, pattern_data: Dict[str, Any]) -> None:
        """Pattern speichern oder updaten."""
        import uuid
        
        # Existierendes Pattern finden
        existing = self._find_similar_pattern(pattern_data)
        
        if existing:
            # Update
            existing.support = pattern_data.get("support", existing.support)
            existing.last_learned = datetime.now(timezone.utc).isoformat()
            existing.update_confidence()
            self._storage.save_pattern(existing)
            _LOGGER.info(f"Pattern updated: {existing.id}")
        else:
            # Neu anlegen
            pattern = Pattern(
                id=f"p_{uuid.uuid4().hex[:8]}",
                description=pattern_data.get("description", "Auto-discovered pattern"),
                trigger=pattern_data["trigger"],
                action=pattern_data["action"],
                support=pattern_data.get("support", 0),
                state=PatternState.OBSERVING,
            )
            self._storage.save_pattern(pattern)
            _LOGGER.info(f"New pattern discovered: {pattern.id}")
    
    def _find_similar_pattern(self, pattern_data: Dict[str, Any]) -> Optional[Pattern]:
        """Ähnliches Pattern finden."""
        all_patterns = self._storage.get_patterns()
        new_trigger = pattern_data.get("trigger", {})
        new_action = pattern_data.get("action", {})
        
        for p in all_patterns:
            # Trigger-Vergleich
            if p.trigger == new_trigger and p.action == new_action:
                return p
        
        return None


# =============================================================================
# Singleton
# =============================================================================

_discovery_instance: Optional[AutoDiscovery] = None


def get_auto_discovery() -> AutoDiscovery:
    """Singleton-Zugriff auf AutoDiscovery."""
    global _discovery_instance
    
    if _discovery_instance is None:
        _discovery_instance = AutoDiscovery()
        _discovery_instance.start()
    
    return _discovery_instance
