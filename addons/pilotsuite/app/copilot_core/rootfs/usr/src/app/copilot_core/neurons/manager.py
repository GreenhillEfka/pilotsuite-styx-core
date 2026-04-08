"""Neuron Manager -- Orchestriert alle Neuronen im neuronalen System.

Der NeuronManager ist verantwortlich fuer:
  - Erstellen und Konfigurieren von Neuronen
  - Ausfuehren der neuronalen Pipeline: Kontext -> Zustand -> Stimmung -> Vorschlaege
  - Verwaltung von State-Updates aus Home Assistant
  - Generierung von Vorschlaegen (Suggestions) basierend auf Mood-Neuronen
  - Bereitstellung API-faehiger Daten

Pipeline-Ablauf:
  1. Kontext-Neuronen auswerten (objektive Umgebungsdaten)
  2. Zustands-Neuronen auswerten (geglaettete Werte)
  3. Mood-Neuronen auswerten (aggregierte Stimmung)
  4. Dominante Stimmung bestimmen
  5. Vorschlaege generieren (inkl. haushaltsbewusster Logik)

Haushaltsbewusste Vorschlaege (wenn HouseholdProfile gesetzt):
  - Kinder allein zuhause: Dringlichkeitsbenachrichtigung + Tueren/Rolllaeden sichern
  - Bettzeit naehert sich: Licht dimmen fuer Kinderzimmer
  - Kinder anwesend: Familienfreundliche Medien-Lautstaerke
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable
from collections import defaultdict
from copilot_core.household import HouseholdProfile

from .base import (
    BaseNeuron, NeuronConfig, NeuronState, NeuronType, MoodType,
    ContextNeuron, StateNeuron, MoodNeuron
)
from .context import (
    PresenceNeuron, TimeOfDayNeuron, LightLevelNeuron, WeatherNeuron,
    create_context_neuron, CONTEXT_NEURON_CLASSES
)
from .state import (
    EnergyLevelNeuron, StressIndexNeuron, RoutineStabilityNeuron,
    SleepDebtNeuron, AttentionLoadNeuron, ComfortIndexNeuron,
    create_state_neuron, STATE_NEURON_CLASSES
)
from .energy import (
    PVForecastNeuron, EnergyCostNeuron, GridOptimizationNeuron,
    create_pv_forecast_neuron, create_energy_cost_neuron,
    create_grid_optimization_neuron, ENERGY_NEURON_CLASSES
)
from .unifi import (
    UniFiContextNeuron, NetworkQuality,
    create_unifi_context_neuron, UNIFI_NEURON_CLASSES
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class NeuralPipelineResult:
    """Ergebnis eines vollstaendigen Pipeline-Durchlaufs.

    Enthaelt Kontext-, Zustands- und Mood-Werte, die dominante Stimmung,
    generierte Vorschlaege und den Zustand aller Neuronen.
    """
    timestamp: str
    context_values: Dict[str, float]
    state_values: Dict[str, float]
    mood_values: Dict[str, float]
    dominant_mood: str
    mood_confidence: float
    suggestions: List[Dict[str, Any]]
    neuron_states: Dict[str, Dict[str, Any]]


class NeuronManager:
    """Manages all neurons and runs the neural pipeline.
    
    Architecture:
        HA States → Context Neurons → State Neurons → Mood Neurons → Suggestions
    
    Usage:
        manager = NeuronManager()
        manager.configure_from_ha(ha_states, config)
        
        # On HA state change
        manager.update_states(new_states)
        
        # Run pipeline
        result = manager.evaluate()
        mood = result.dominant_mood
    """
    
    def __init__(self):
        """Initialize the neuron manager."""
        # Neuron storage by type
        self._context_neurons: Dict[str, ContextNeuron] = {}
        self._state_neurons: Dict[str, StateNeuron] = {}
        self._mood_neurons: Dict[str, MoodNeuron] = {}
        
        # Current HA states
        self._ha_states: Dict[str, Any] = {}
        
        # Evaluation context
        self._context: Dict[str, Any] = {}
        
        # Callbacks
        self._on_mood_change: Optional[Callable[[str, float], None]] = None
        self._on_suggestion: Optional[Callable[[Dict], None]] = None
        
        # Last result
        self._last_result: Optional[NeuralPipelineResult] = None
        
        # Mood history for smoothing
        self._mood_history: List[Dict[str, float]] = []
        self._history_max: int = 10

        # Household profile (optional)
        self._household: Optional[HouseholdProfile] = None

        _LOGGER.info("NeuronManager initialized")
    
    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    
    def configure_from_ha(
        self,
        ha_states: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Configure neurons from Home Assistant states and config.
        
        Args:
            ha_states: Current HA states dict
            config: Optional neuron configuration
        """
        self._ha_states = ha_states
        config = config or {}
        
        # Create default context neurons
        self._create_default_context_neurons(config.get("context_neurons", {}))
        
        # Create default state neurons
        self._create_default_state_neurons(config.get("state_neurons", {}))
        
        # Create mood neurons
        self._create_mood_neurons(config.get("mood_neurons", {}))
        
        # Create energy neurons (optional, requires HA entities)
        self._create_energy_neurons(config.get("energy_neurons", {}))
        
        # Create UniFi neurons (optional, requires HA entities)
        self._create_unifi_neurons(config.get("unifi_neurons", {}))
        
        _LOGGER.info(
            "Configured %d context, %d state, %d mood neurons",
            len(self._context_neurons),
            len(self._state_neurons),
            len(self._mood_neurons)
        )
    
    def _create_default_context_neurons(self, config: Dict[str, Any]) -> None:
        """Create default context neurons."""
        # Presence neuron
        self.add_neuron("context", "presence", PresenceNeuron(NeuronConfig(
            name="presence",
            neuron_type=NeuronType.CONTEXT,
            entity_ids=config.get("presence", {}).get("entity_ids", ["person.home"]),
            weights={"zone": config.get("presence", {}).get("zone", "house")}
        )))
        
        # Time of day neuron
        self.add_neuron("context", "time_of_day", TimeOfDayNeuron(NeuronConfig(
            name="time_of_day",
            neuron_type=NeuronType.CONTEXT,
            weights={"timezone": config.get("time_of_day", {}).get("timezone", "Europe/Berlin")}
        )))
        
        # Light level neuron
        self.add_neuron("context", "light_level", LightLevelNeuron(NeuronConfig(
            name="light_level",
            neuron_type=NeuronType.CONTEXT,
            entity_ids=config.get("light_level", {}).get("entity_ids", []),
            weights={"use_sun_position": config.get("light_level", {}).get("use_sun_position", True)}
        )))
        
        # Weather neuron
        self.add_neuron("context", "weather", WeatherNeuron(NeuronConfig(
            name="weather",
            neuron_type=NeuronType.CONTEXT,
            entity_ids=config.get("weather", {}).get("entity_ids", ["weather.home"])
        )))
    
    def _create_default_state_neurons(self, config: Dict[str, Any]) -> None:
        """Create default state neurons."""
        for name in STATE_NEURON_CLASSES:
            neuron_config = config.get(name, {})
            self.add_neuron("state", name, create_state_neuron(name, NeuronConfig(
                name=name,
                neuron_type=NeuronType.STATE,
                **neuron_config
            )))
    
    def _create_mood_neurons(self, config: Dict[str, Any]) -> None:
        """Create mood neurons."""
        from .mood import (
            RelaxMoodNeuron, FocusMoodNeuron, ActiveMoodNeuron, SleepMoodNeuron,
            AwayMoodNeuron, AlertMoodNeuron, SocialMoodNeuron, RecoveryMoodNeuron,
            MOOD_NEURON_CLASSES
        )
        
        for name, neuron_class in MOOD_NEURON_CLASSES.items():
            neuron_config = config.get(name, {})
            self.add_neuron("mood", name, neuron_class(NeuronConfig(
                name=name,
                neuron_type=NeuronType.MOOD,
                **neuron_config
            )))
    
    def _create_energy_neurons(self, config: Dict[str, Any]) -> None:
        """Create energy neurons for PV/cost optimization.
        
        Energy neurons are optional and require HA entities:
        - pv_forecast: PV production entity
        - energy_cost: Electricity price entity
        - grid_optimization: Grid import/export entity
        """
        # PV Forecast Neuron
        pv_config = config.get("pv_forecast", {})
        if pv_config.get("enabled", False):
            self.add_neuron("state", "pv_forecast", create_pv_forecast_neuron(
                pv_entity=pv_config.get("pv_entity"),
                battery_entity=pv_config.get("battery_entity"),
                weather_entity=pv_config.get("weather_entity"),
                pv_capacity_kw=pv_config.get("pv_capacity_kw", 10.0),
                name="PV Forecast"
            ))
        
        # Energy Cost Neuron
        cost_config = config.get("energy_cost", {})
        if cost_config.get("enabled", False):
            self.add_neuron("state", "energy_cost", create_energy_cost_neuron(
                price_entity=cost_config.get("price_entity"),
                peak_hours=cost_config.get("peak_hours"),
                name="Energy Cost"
            ))
        
        # Grid Optimization Neuron
        grid_config = config.get("grid_optimization", {})
        if grid_config.get("enabled", False):
            self.add_neuron("state", "grid_optimization", create_grid_optimization_neuron(
                pv_entity=grid_config.get("pv_entity"),
                battery_entity=grid_config.get("battery_entity"),
                grid_entity=grid_config.get("grid_entity"),
                price_entity=grid_config.get("price_entity"),
                name="Grid Optimization"
            ))
        
        _LOGGER.info(
            "Configured %d energy neurons",
            sum(1 for n in ["pv_forecast", "energy_cost", "grid_optimization"] if n in self._state_neurons)
        )
    
    def _create_unifi_neurons(self, config: Dict[str, Any]) -> None:
        """Create UniFi network context neurons.
        
        UniFi neurons are optional and require HA entities:
        - wan_entity: WAN status sensor
        - latency_entity: Latency sensor (ms)
        - packet_loss_entity: Packet loss sensor (%)
        """
        unifi_config = config.get("unifi_context", {})
        if unifi_config.get("enabled", False):
            self.add_neuron("context", "unifi_context", create_unifi_context_neuron(
                wan_entity=unifi_config.get("wan_entity"),
                latency_entity=unifi_config.get("latency_entity"),
                packet_loss_entity=unifi_config.get("packet_loss_entity"),
                latency_warning_ms=unifi_config.get("latency_warning_ms", 50.0),
                latency_critical_ms=unifi_config.get("latency_critical_ms", 100.0),
                loss_warning_percent=unifi_config.get("loss_warning_percent", 1.0),
                loss_critical_percent=unifi_config.get("loss_critical_percent", 3.0),
                name="UniFi Network"
            ))
            _LOGGER.info("Configured UniFi context neuron")
    
    # -------------------------------------------------------------------------
    # Neuron Management
    # -------------------------------------------------------------------------
    
    def add_neuron(self, neuron_type: str, name: str, neuron: BaseNeuron) -> None:
        """Add a neuron to the manager.
        
        Args:
            neuron_type: "context", "state", or "mood"
            name: Unique neuron name
            neuron: Neuron instance
        """
        if neuron_type == "context":
            self._context_neurons[name] = neuron
        elif neuron_type == "state":
            self._state_neurons[name] = neuron
        elif neuron_type == "mood":
            self._mood_neurons[name] = neuron
        else:
            raise ValueError(f"Unknown neuron type: {neuron_type}")
        
        _LOGGER.debug("Added %s neuron: %s", neuron_type, name)
    
    def get_neuron(self, name: str) -> Optional[BaseNeuron]:
        """Get a neuron by name."""
        return (
            self._context_neurons.get(name) or
            self._state_neurons.get(name) or
            self._mood_neurons.get(name)
        )
    
    def get_all_neurons(self) -> Dict[str, BaseNeuron]:
        """Get all neurons."""
        return {
            **{f"context.{k}": v for k, v in self._context_neurons.items()},
            **{f"state.{k}": v for k, v in self._state_neurons.items()},
            **{f"mood.{k}": v for k, v in self._mood_neurons.items()},
        }
    
    def get_neurons_by_type(self, neuron_type: NeuronType) -> Dict[str, BaseNeuron]:
        """Get neurons by type."""
        if neuron_type == NeuronType.CONTEXT:
            return self._context_neurons.copy()
        elif neuron_type == NeuronType.STATE:
            return self._state_neurons.copy()
        elif neuron_type == NeuronType.MOOD:
            return self._mood_neurons.copy()
        return {}
    
    # -------------------------------------------------------------------------
    # State Updates
    # -------------------------------------------------------------------------
    
    def update_states(self, ha_states: Dict[str, Any]) -> None:
        """Update Home Assistant states.
        
        This should be called whenever HA states change.
        The neurons will use these states on the next evaluate().
        """
        self._ha_states.update(ha_states)
        _LOGGER.debug("Updated %d HA states", len(ha_states))
    
    def set_context(self, context: Dict[str, Any]) -> None:
        """Set additional context for evaluation.

        This can include:
        - presence: Presence data by zone
        - sun: Sun position data
        - weather: Weather data
        - history: Historical patterns
        - now: Current timestamp
        """
        self._context.update(context)

    def set_household(self, profile: HouseholdProfile) -> None:
        """Setzt das Haushaltsprofil fuer altersabhaengige Vorschlaege.

        Nach dem Setzen werden bei jeder Evaluation haushaltsbewusste
        Vorschlaege generiert (z.B. Kinder allein, Bettzeit, Lautstaerke).
        """
        self._household = profile
        _LOGGER.info("Household profile set with %d members", len(profile.members))
    
    # -------------------------------------------------------------------------
    # Pipeline Execution
    # -------------------------------------------------------------------------
    
    def evaluate(self) -> NeuralPipelineResult:
        """Fuehrt die vollstaendige neuronale Pipeline aus.

        Pipeline-Schritte:
          1. Kontext-Neuronen auswerten (objektive Umgebungsdaten)
          2. Zustands-Neuronen auswerten (geglaettete Werte)
          3. Mood-Neuronen auswerten (aggregierte Stimmung)
          4. Dominante Stimmung bestimmen (mit Glaettung ueber Historie)
          5. Vorschlaege generieren (stimmungs- und haushaltsbezogen)

        Returns:
            NeuralPipelineResult mit allen Werten und Vorschlaegen.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Anwesende Personen aus HA-States ableiten
        present_persons: List[str] = []
        for eid, state_val in self._ha_states.items():
            if eid.startswith("person."):
                st = state_val if isinstance(state_val, str) else (
                    state_val.get("state", "") if isinstance(state_val, dict) else ""
                )
                if st == "home":
                    present_persons.append(eid)

        # Haushaltszusammenfassung erstellen, falls Profil gesetzt
        household_summary: Dict[str, Any] = {}
        if self._household:
            household_summary = self._household.presence_summary(present_persons)

        # Evaluierungskontext aufbauen
        eval_context = {
            "states": self._ha_states,
            "now": self._context.get("now", datetime.now(timezone.utc)),
            "presence": self._context.get("presence", {}),
            "sun": self._context.get("sun", {}),
            "weather": self._context.get("weather", {}),
            "history": self._context.get("history", {}),
            "neurons": {},  # Will be filled with neuron outputs
            "household": household_summary,
            "present_persons": present_persons,
        }
        
        # 1. Kontext-Neuronen auswerten
        context_values = {}
        for name, neuron in self._context_neurons.items():
            try:
                value = neuron.evaluate(eval_context)
                neuron.update(value)
                context_values[name] = neuron.value
                eval_context["neurons"][f"context.{name}"] = neuron.state.to_dict()
            except Exception as e:
                _LOGGER.error("Error evaluating context neuron %s: %s", name, e)
                context_values[name] = 0.5
        
        # 2. Zustands-Neuronen auswerten (nutzt Kontext-Werte)
        eval_context["context_values"] = context_values
        state_values = {}
        for name, neuron in self._state_neurons.items():
            try:
                value = neuron.evaluate(eval_context)
                neuron.update(value)
                state_values[name] = neuron.value
                eval_context["neurons"][f"state.{name}"] = neuron.state.to_dict()
            except Exception as e:
                _LOGGER.error("Error evaluating state neuron %s: %s", name, e)
                state_values[name] = 0.5
        
        # 3. Mood-Neuronen auswerten (nutzt Kontext- und Zustands-Werte)
        eval_context["state_values"] = state_values
        mood_values = {}
        for name, neuron in self._mood_neurons.items():
            try:
                value = neuron.evaluate(eval_context)
                neuron.update(value)
                mood_values[name] = neuron.value
                eval_context["neurons"][f"mood.{name}"] = neuron.state.to_dict()
            except Exception as e:
                _LOGGER.error("Error evaluating mood neuron %s: %s", name, e)
                mood_values[name] = 0.0
        
        # 4. Dominante Stimmung bestimmen
        dominant_mood, confidence = self._determine_mood(mood_values)
        
        # 5. Vorschlaege generieren
        suggestions = self._generate_suggestions(dominant_mood, mood_values, eval_context)
        
        # Ergebnis zusammenbauen
        neuron_states = {
            name: neuron.state.to_dict()
            for name, neuron in self.get_all_neurons().items()
        }
        
        result = NeuralPipelineResult(
            timestamp=timestamp,
            context_values=context_values,
            state_values=state_values,
            mood_values=mood_values,
            dominant_mood=dominant_mood,
            mood_confidence=confidence,
            suggestions=suggestions,
            neuron_states=neuron_states,
        )
        
        # Stimmungswechsel pruefen und Callback auslösen
        if self._last_result and self._last_result.dominant_mood != dominant_mood:
            self._on_mood_changed(dominant_mood, confidence)
        
        # Vorschlags-Callbacks ausfuehren
        for suggestion in suggestions:
            if self._on_suggestion:
                self._on_suggestion(suggestion)
        
        self._last_result = result
        self._mood_history.append(mood_values)
        if len(self._mood_history) > self._history_max:
            self._mood_history.pop(0)
        
        _LOGGER.info(
            "Neural pipeline: mood=%s (%.2f), suggestions=%d",
            dominant_mood, confidence, len(suggestions)
        )
        
        return result
    
    def _determine_mood(self, mood_values: Dict[str, float]) -> tuple:
        """Bestimmt die dominante Stimmung aus den Mood-Werten.

        Verwendet eine geglaettete Historie (letzte 3 Werte), um schnelle
        Stimmungswechsel zu vermeiden.

        Returns:
            Tuple (mood_name, confidence).
        """
        if not mood_values:
            return "relax", 0.0
        
        # Glaettung ueber die Historie anwenden
        if self._mood_history:
            smoothed = {}
            for mood, value in mood_values.items():
                history_values = [h.get(mood, 0) for h in self._mood_history[-3:]]
                history_values.append(value)
                smoothed[mood] = sum(history_values) / len(history_values)
            mood_values = smoothed
        
        # Dominante Stimmung ermitteln (hoechster Wert)
        dominant_mood = max(mood_values, key=mood_values.get)
        confidence = mood_values[dominant_mood]
        
        return dominant_mood, confidence
    
    def _get_entities_by_domain(
        self, context: Dict[str, Any], domain: str
    ) -> List[str]:
        """Get entity IDs from HA states matching a domain."""
        states = context.get("states", {})
        return [
            eid for eid in states
            if eid.startswith(f"{domain}.")
        ]

    def _get_entities_by_zone(
        self, context: Dict[str, Any], domain: str, zone: str
    ) -> List[str]:
        """Get entity IDs from HA states matching domain and zone/area."""
        states = context.get("states", {})
        entities = []
        for eid, state in states.items():
            if not eid.startswith(f"{domain}."):
                continue
            attrs = state if isinstance(state, dict) else {}
            area = attrs.get("area_id", "") or attrs.get("friendly_name", "")
            if zone.lower() in area.lower():
                entities.append(eid)
        # Fallback: all domain entities if no zone match
        return entities if entities else self._get_entities_by_domain(context, domain)

    def _build_action(
        self,
        domain: str,
        action: str,
        context: Dict[str, Any],
        granularity: str = "all",
        zone: str | None = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        """Build a suggestion action with entity targeting.

        Args:
            domain: HA domain (light, media_player, climate, ...)
            action: Service action (turn_on, turn_off, ...)
            context: Evaluation context containing HA states
            granularity: 'all' | 'zone' | 'entity'
            zone: Zone/area name for zone-level targeting
            **extra: Additional service data (brightness_pct, volume_level, ...)

        Returns:
            Action dict with entity_ids and granularity metadata
        """
        if zone and granularity == "zone":
            entity_ids = self._get_entities_by_zone(context, domain, zone)
        else:
            entity_ids = self._get_entities_by_domain(context, domain)

        result: Dict[str, Any] = {
            "domain": domain,
            "action": action,
            "entity_ids": entity_ids,
            "granularity": granularity,
        }
        if zone:
            result["zone"] = zone
        result.update(extra)
        return result

    def _generate_suggestions(
        self,
        dominant_mood: str,
        mood_values: Dict[str, float],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generiert zone-aware Vorschlaege basierend auf Stimmung und Haushalt.

        Jeder Vorschlag enthaelt entity_ids, granularity und zone.
        Zwei Vorschlagsquellen:
          1. Stimmungsbasiert: relax, focus, sleep, away, alert
          2. Haushaltsbewusst (wenn HouseholdProfile gesetzt):
             - Kinder allein zuhause: DRINGENDE Sicherheitsbenachrichtigung
             - Bettzeit naehert sich: Licht dimmen
             - Kinder anwesend: Familienfreundliche Lautstaerke

        Args:
            dominant_mood: Aktuelle dominante Stimmung.
            mood_values: Alle Mood-Werte.
            context: Evaluierungskontext inkl. Haushaltsdaten.

        Returns:
            Liste von Vorschlags-Dicts mit Entity-spezifischen Aktionen.
        """
        suggestions = []

        # Kontextwerte auslesen
        light_level = context.get("context_values", {}).get("light_level", 0.5)
        presence = context.get("context_values", {}).get("presence", 0.5)
        time_of_day = context.get("context_values", {}).get("time_of_day", 0.5)

        # Aktive Praesenz-Zonen fuer zone-aware Vorschlaege erkennen
        presence_data = context.get("presence", {})
        active_zones = [
            z for z, v in presence_data.items()
            if isinstance(v, (int, float)) and v > 0.5
        ] if presence_data else []

        # Stimmungsbasierte Vorschlaege generieren
        if dominant_mood == "relax":
            if light_level > 0.6:
                zone = active_zones[0] if active_zones else None
                suggestions.append({
                    "type": "action",
                    "mood": "relax",
                    "suggestion": f"Dim lights for relaxation{f' in {zone}' if zone else ''}",
                    "actions": [
                        self._build_action(
                            "light", "turn_on", context,
                            granularity="zone" if zone else "all",
                            zone=zone,
                            brightness_pct=30,
                        ),
                    ],
                    "confidence": mood_values.get("relax", 0.5),
                    "priority": "low",
                })

        elif dominant_mood == "focus":
            zone = active_zones[0] if active_zones else None
            suggestions.append({
                "type": "action",
                "mood": "focus",
                "suggestion": f"Optimize environment for focus{f' in {zone}' if zone else ''}",
                "actions": [
                    self._build_action(
                        "light", "turn_on", context,
                        granularity="zone" if zone else "all",
                        zone=zone,
                        brightness_pct=80,
                    ),
                    self._build_action(
                        "media_player", "volume_set", context,
                        granularity="zone" if zone else "all",
                        zone=zone,
                        volume_level=0.2,
                    ),
                ],
                "confidence": mood_values.get("focus", 0.5),
                "priority": "medium",
            })

        elif dominant_mood == "sleep":
            suggestions.append({
                "type": "action",
                "mood": "sleep",
                "suggestion": "Prepare for sleep",
                "actions": [
                    self._build_action("light", "turn_off", context, granularity="all"),
                    self._build_action("media_player", "turn_off", context, granularity="all"),
                ],
                "confidence": mood_values.get("sleep", 0.5),
                "priority": "high",
            })

        elif dominant_mood == "away":
            suggestions.append({
                "type": "action",
                "mood": "away",
                "suggestion": "Away mode - secure home",
                "actions": [
                    self._build_action("light", "turn_off", context, granularity="all"),
                    self._build_action(
                        "climate", "set_preset_mode", context,
                        granularity="all",
                        preset_mode="away",
                    ),
                ],
                "confidence": mood_values.get("away", 0.5),
                "priority": "medium",
            })

        elif dominant_mood == "alert":
            suggestions.append({
                "type": "notification",
                "mood": "alert",
                "suggestion": "Alert detected - check environment",
                "confidence": mood_values.get("alert", 0.5),
                "priority": "high",
            })

        # ----- Haushaltsbewusste Vorschlaege -----
        household = context.get("household", {})
        if household:
            # Kinder allein zuhause -> DRINGENDE Sicherheitsbenachrichtigung
            if household.get("only_children_home"):
                suggestions.append({
                    "type": "notification",
                    "mood": "alert",
                    "suggestion": "URGENT: Only children are home without adult supervision",
                    "actions": [
                        {"domain": "lock", "action": "lock"},
                        {"domain": "cover", "action": "close_cover"},
                    ],
                    "confidence": 1.0,
                    "priority": "urgent",
                })

            # Bettzeit naehert sich -> Licht in Kinderzimmern dimmen
            now_dt = context.get("now", datetime.now(timezone.utc))
            current_hour = now_dt.hour if hasattr(now_dt, "hour") else 20
            earliest_bed = household.get("earliest_bedtime_hour", 23)
            if household.get("children_home") and 0 < earliest_bed - current_hour <= 1:
                suggestions.append({
                    "type": "action",
                    "mood": "sleep",
                    "suggestion": "Bedtime approaching for children - dimming lights",
                    "actions": [
                        {"domain": "light", "action": "turn_on", "brightness_pct": 20},
                    ],
                    "confidence": 0.9,
                    "priority": "medium",
                })

            # Kinder anwesend -> Lautstaerke auf familienfreundliches Niveau
            if household.get("children_home"):
                suggestions.append({
                    "type": "action",
                    "mood": "social",
                    "suggestion": "Children present - set family-friendly media volume",
                    "actions": [
                        {"domain": "media_player", "action": "volume_set", "volume_level": 0.3},
                    ],
                    "confidence": 0.8,
                    "priority": "low",
                })

        return suggestions
    
    # -------------------------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------------------------
    
    def on_mood_change(self, callback: Callable[[str, float], None]) -> None:
        """Register callback for mood changes."""
        self._on_mood_change = callback
    
    def on_suggestion(self, callback: Callable[[Dict], None]) -> None:
        """Register callback for suggestions."""
        self._on_suggestion = callback
    
    def _on_mood_changed(self, new_mood: str, confidence: float) -> None:
        """Handle mood change."""
        _LOGGER.info("Mood changed to: %s (%.2f)", new_mood, confidence)
        if self._on_mood_change:
            try:
                self._on_mood_change(new_mood, confidence)
            except Exception as e:
                _LOGGER.error("Mood change callback error: %s", e)
    
    # -------------------------------------------------------------------------
    # API Helpers
    # -------------------------------------------------------------------------
    
    def get_mood_summary(self) -> Dict[str, Any]:
        """Get a summary of current mood state for API."""
        if not self._last_result:
            self.evaluate()
        
        if not self._last_result:
            return {"mood": "unknown", "confidence": 0.0}
        
        return {
            "mood": self._last_result.dominant_mood,
            "confidence": self._last_result.mood_confidence,
            "mood_values": self._last_result.mood_values,
            "timestamp": self._last_result.timestamp,
        }
    
    def get_neuron_summary(self) -> Dict[str, Any]:
        """Get a summary of all neurons for API."""
        return {
            "context": {
                name: neuron.state.to_dict()
                for name, neuron in self._context_neurons.items()
            },
            "state": {
                name: neuron.state.to_dict()
                for name, neuron in self._state_neurons.items()
            },
            "mood": {
                name: neuron.state.to_dict()
                for name, neuron in self._mood_neurons.items()
            },
            "total_count": (
                len(self._context_neurons) +
                len(self._state_neurons) +
                len(self._mood_neurons)
            ),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager state for API."""
        return {
            "context_neurons": list(self._context_neurons.keys()),
            "state_neurons": list(self._state_neurons.keys()),
            "mood_neurons": list(self._mood_neurons.keys()),
            "ha_states_count": len(self._ha_states),
            "last_evaluation": self._last_result.timestamp if self._last_result else None,
            "current_mood": self.get_mood_summary(),
        }


# Singleton instance
_manager_instance: Optional[NeuronManager] = None


def get_neuron_manager() -> NeuronManager:
    """Get the singleton NeuronManager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = NeuronManager()
    return _manager_instance


def reset_neuron_manager() -> None:
    """Reset the singleton NeuronManager (for testing)."""
    global _manager_instance
    _manager_instance = None


__all__ = [
    "NeuronManager",
    "NeuralPipelineResult",
    "get_neuron_manager",
    "reset_neuron_manager",
]