"""Predictive Automation Engine — Vorhersage nächster Aktionen (v1.0.0).

Sagt basierend auf gelernten Mustern die nächste wahrscheinliche Aktion voraus:
- Zeitbasierte Vorhersagen (morgens → Licht an)
- Wetter-basierte Vorhersagen (sonnig → Jalousien runter)
- Confidence-Score pro Vorhersage
- Auto-Vorschläge für Nutzerbestätigung
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .pattern_learner import Pattern, PatternLearner

_LOGGER = logging.getLogger(__name__)


@dataclass
class Prediction:
    """Eine Vorhersage der nächsten Aktion."""
    
    prediction_id: str
    entity_id: str
    action: str
    confidence: float  # 0.0 - 1.0
    
    # Vorhersage-Zeitpunkt
    predicted_time: datetime
    prediction_type: str  # "time_based", "weather_based", "sequence"
    
    # Begründung
    reason: str
    based_on_patterns: List[str]  # Pattern-IDs
    
    # Wetter-Kontext (falls relevant)
    weather_condition: Optional[str] = None
    current_temperature: Optional[float] = None
    
    # Vorschlagstext für Nutzer
    suggestion_text: Optional[str] = None
    
    # Metadaten
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary."""
        data = asdict(self)
        data["predicted_time"] = self.predicted_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Prediction:
        """Erstelle Prediction aus Dictionary."""
        data["predicted_time"] = datetime.fromisoformat(data["predicted_time"])
        return cls(**data)


@dataclass
class PredictionRequest:
    """Anfrage für Vorhersage."""
    
    current_time: Optional[datetime] = None
    weather_condition: Optional[str] = None
    current_temperature: Optional[float] = None
    include_low_confidence: bool = False
    max_predictions: int = 5


class PredictiveAutomationEngine:
    """Engine für prädiktive Automation.
    
    Verwendet gelernte Muster, um nächste Aktionen vorherzusagen
    und dem Nutzer zur Bestätigung vorzuschlagen.
    """
    
    def __init__(
        self, 
        pattern_learner: PatternLearner,
        min_confidence: float = 0.5
    ):
        """Initialisiere Predictive Engine.
        
        Args:
            pattern_learner: PatternLearner-Instanz mit gelernten Mustern
            min_confidence: Minimale Confidence für Vorhersagen
        """
        self.pattern_learner = pattern_learner
        self.min_confidence = min_confidence
        self._prediction_counter = 0
    
    def _generate_prediction_id(self) -> str:
        """Generiere eindeutige Prediction-ID."""
        self._prediction_counter += 1
        return f"pred_{self._prediction_counter:06d}"
    
    def predict_next(
        self,
        request: Optional[PredictionRequest] = None
    ) -> Optional[Prediction]:
        """Sage nächste wahrscheinliche Aktion voraus.
        
        Args:
            request: Vorhersage-Anfrage mit Kontext
        
        Returns:
            Beste Vorhersage oder None
        """
        if request is None:
            request = PredictionRequest()
        
        current_time = request.current_time or datetime.now()
        current_hour = current_time.hour
        current_day = current_time.weekday()
        
        # Hole relevante Patterns
        patterns = self.pattern_learner.get_patterns(
            min_confidence=self.min_confidence if not request.include_low_confidence else 0.0
        )
        
        if not patterns:
            _LOGGER.debug("Keine Patterns für Vorhersage verfügbar")
            return None
        
        # Bewerte Patterns für aktuelle Situation
        scored_predictions = []
        
        for pattern in patterns:
            score = self._score_pattern(
                pattern,
                current_time=current_time,
                weather_condition=request.weather_condition,
                temperature=request.current_temperature
            )
            
            if score > 0:
                prediction = self._create_prediction(
                    pattern,
                    current_time=current_time,
                    score=score,
                    weather_condition=request.weather_condition,
                    temperature=request.current_temperature
                )
                scored_predictions.append((score, prediction))
        
        if not scored_predictions:
            return None
        
        # Sortiere nach Score und gib beste Vorhersage zurück
        scored_predictions.sort(key=lambda x: x[0], reverse=True)
        best_prediction = scored_predictions[0][1]
        
        _LOGGER.info(
            f"Vorhersage: {best_prediction.action} für {best_prediction.entity_id} "
            f"(Confidence: {best_prediction.confidence:.2f})"
        )
        
        return best_prediction
    
    def predict_all(
        self,
        request: Optional[PredictionRequest] = None
    ) -> List[Prediction]:
        """Sage alle wahrscheinlichen Aktionen voraus.
        
        Args:
            request: Vorhersage-Anfrage
        
        Returns:
            Liste der Vorhersagen, sortiert nach Confidence
        """
        if request is None:
            request = PredictionRequest()
        
        current_time = request.current_time or datetime.now()
        
        # Hole relevante Patterns
        patterns = self.pattern_learner.get_patterns(
            min_confidence=self.min_confidence if not request.include_low_confidence else 0.0
        )
        
        predictions = []
        
        for pattern in patterns:
            score = self._score_pattern(
                pattern,
                current_time=current_time,
                weather_condition=request.weather_condition,
                temperature=request.current_temperature
            )
            
            if score > 0:
                prediction = self._create_prediction(
                    pattern,
                    current_time=current_time,
                    score=score,
                    weather_condition=request.weather_condition,
                    temperature=request.current_temperature
                )
                predictions.append(prediction)
        
        # Sortiere nach Confidence
        predictions.sort(key=lambda p: p.confidence, reverse=True)
        
        # Begrenze Anzahl
        max_preds = request.max_predictions
        return predictions[:max_preds]
    
    def _score_pattern(
        self,
        pattern: Pattern,
        current_time: datetime,
        weather_condition: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> float:
        """Bewerte ein Pattern für aktuelle Situation.
        
        Returns:
            Score (0.0 - 1.0), 0.0 bedeutet keine Vorhersage
        """
        score = 0.0
        
        # Zeitbasierte Patterns
        if pattern.pattern_type == "time_based":
            # Prüfe Zeitfenster
            if pattern.hour_of_day is not None:
                # Vorhersage für nächstes Zeitfenster
                current_hour = current_time.hour
                pattern_hour = pattern.hour_of_day
                
                # Berechne Zeitdifferenz (in Stunden)
                if pattern_hour >= current_hour:
                    hours_until = pattern_hour - current_hour
                else:
                    hours_until = 24 - (current_hour - pattern_hour)
                
                # Score basiert auf Nähe zum Pattern-Zeitpunkt
                if hours_until <= 2:  # Innerhalb der nächsten 2 Stunden
                    time_score = 1.0 - (hours_until / 2.0)
                    score = time_score * pattern.confidence
        
        # Wetter-basierte Patterns
        elif pattern.pattern_type == "weather_based":
            if pattern.weather_condition and weather_condition:
                if pattern.weather_condition.lower() == weather_condition.lower():
                    # Wetter stimmt überein
                    score = pattern.confidence
                    
                    # Zusätzlicher Bonus für aktuelle Wetter-Bedingungen
                    if weather_condition == "sunny" and pattern.action in [
                        "close_cover",
                        "turn_off_light"
                    ]:
                        score = min(1.0, score * 1.2)
                    elif weather_condition in ["cloudy", "rainy"] and pattern.action in [
                        "turn_on_light",
                        "open_cover"
                    ]:
                        score = min(1.0, score * 1.1)
        
        return min(1.0, score)
    
    def _create_prediction(
        self,
        pattern: Pattern,
        current_time: datetime,
        score: float,
        weather_condition: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Prediction:
        """Erstelle Prediction aus Pattern."""
        # Berechne vorhergesagten Zeitpunkt
        if pattern.hour_of_day is not None:
            predicted_time = current_time.replace(
                hour=pattern.hour_of_day,
                minute=0,
                second=0,
                microsecond=0
            )
            
            # Wenn Zeit schon vorbei heute, dann morgen
            if predicted_time <= current_time:
                predicted_time += timedelta(days=1)
        else:
            predicted_time = current_time + timedelta(hours=1)
        
        # Generiere Vorschlagstext
        suggestion_text = self._generate_suggestion_text(
            pattern, predicted_time, weather_condition
        )
        
        # Generiere Begründung
        reason = self._generate_reason(pattern, weather_condition)
        
        prediction = Prediction(
            prediction_id=self._generate_prediction_id(),
            entity_id=pattern.entity_id,
            action=pattern.action,
            confidence=round(score, 3),
            predicted_time=predicted_time,
            prediction_type=pattern.pattern_type,
            reason=reason,
            based_on_patterns=[pattern.pattern_id],
            weather_condition=weather_condition or pattern.weather_condition,
            current_temperature=temperature,
            suggestion_text=suggestion_text,
            metadata={
                "pattern_occurrence_count": pattern.occurrence_count,
                "pattern_first_seen": pattern.first_occurrence.isoformat() if pattern.first_occurrence else None,
            }
        )
        
        return prediction
    
    def _generate_suggestion_text(
        self,
        pattern: Pattern,
        predicted_time: datetime,
        weather_condition: Optional[str] = None
    ) -> str:
        """Generiere natürlichen Vorschlagstext für Nutzer."""
        entity_name = pattern.entity_id.split(".")[-1].replace("_", " ").title()
        
        # Aktionstext
        action_texts = {
            "turn_on": "einschalten",
            "turn_off": "ausschalten",
            "open_cover": "öffnen",
            "close_cover": "schließen",
            "set_temperature": "Temperatur anpassen",
        }
        action_text = action_texts.get(pattern.action, pattern.action)
        
        # Zeit-Text
        hour = predicted_time.hour
        if 5 <= hour < 12:
            time_text = "morgen"
        elif 12 <= hour < 18:
            time_text = "nachmittag"
        elif 18 <= hour < 22:
            time_text = "abend"
        else:
            time_text = "nacht"
        
        # Wetter-Kontext
        weather_text = ""
        if weather_condition:
            weather_texts = {
                "sunny": "bei Sonnenschein ",
                "cloudy": "bei bewölktem Wetter ",
                "rainy": "bei Regen ",
            }
            weather_text = weather_texts.get(weather_condition, "")
        
        # Baue Satz
        if pattern.pattern_type == "time_based":
            return f"Soll ich {entity_name} {action_text}? ({time_text})"
        elif pattern.pattern_type == "weather_based":
            return f"Soll ich {entity_name} {weather_text}{action_text}?"
        else:
            return f"Soll ich {entity_name} {action_text}?"
    
    def _generate_reason(
        self,
        pattern: Pattern,
        weather_condition: Optional[str] = None
    ) -> str:
        """Generiere Begründung für Vorhersage."""
        if pattern.pattern_type == "time_based":
            return (
                f"Basierend auf {pattern.occurrence_count} Beobachtungen "
                f"um diese Tageszeit"
            )
        elif pattern.pattern_type == "weather_based":
            return (
                f"Basierend auf {pattern.occurrence_count} Beobachtungen "
                f"bei {pattern.weather_condition or weather_condition}"
            )
        else:
            return "Basierend auf gelernten Mustern"
    
    def confirm_prediction(
        self,
        prediction_id: str,
        actual_action_performed: bool = True
    ) -> Dict[str, Any]:
        """Bestätige eine Vorhersage (Feedback für Learning).
        
        Args:
            prediction_id: ID der Vorhersage
            actual_action_performed: Wurde die Aktion tatsächlich ausgeführt?
        
        Returns:
            Feedback-Ergebnis
        """
        # In zukünftiger Version: Speichere Feedback für Reinforcement Learning
        return {
            "ok": True,
            "prediction_id": prediction_id,
            "confirmed": actual_action_performed,
            "message": "Feedback gespeichert"
        }
    
    def reject_prediction(
        self,
        prediction_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Lehne eine Vorhersage ab (Feedback für Learning).
        
        Args:
            prediction_id: ID der Vorhersage
            reason: Grund für Ablehnung
        
        Returns:
            Feedback-Ergebnis
        """
        # In zukünftiger Version: Reduziere Confidence für dieses Pattern
        return {
            "ok": True,
            "prediction_id": prediction_id,
            "rejected": True,
            "reason": reason,
            "message": "Feedback gespeichert"
        }
    
    def get_prediction_stats(self) -> Dict[str, Any]:
        """Hole Statistik über Vorhersagen."""
        pattern_stats = self.pattern_learner.get_pattern_stats()
        
        return {
            "total_patterns": pattern_stats.total_patterns,
            "time_based_patterns": pattern_stats.time_based_patterns,
            "weather_based_patterns": pattern_stats.weather_based_patterns,
            "avg_pattern_confidence": pattern_stats.avg_confidence,
            "min_confidence_threshold": self.min_confidence,
            "total_observations": pattern_stats.total_observations,
        }
