"""Predictive Automation System for Smart Home.

Provides:
- ML-based prediction of user actions
- Automatic automation suggestions based on behavior
- Integration with Brain Architecture
- Pattern recognition for home automation
"""

from __future__ import annotations

import logging
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

_LOGGER = logging.getLogger(__name__)


@dataclass
class UserAction:
    """Represents a user action with context."""
    action: str
    timestamp: datetime
    location: str
    entities: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class Prediction:
    """Represents a prediction result."""
    predicted_action: str
    confidence: float
    suggested_automation: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class PredictiveAutomation:
    """Predicts user actions and suggests automations based on behavior patterns."""
    
    def __init__(
        self,
        brain_graph: Optional[Any] = None,
        model_path: str = "/data/predictive_model.pkl",
        pattern_path: str = "/data/prediction_patterns.pkl"
    ):
        """Initialize predictive automation.
        
        Args:
            brain_graph: Brain graph instance for context (optional)
            model_path: Path to save/load ML model
            pattern_path: Path to save/load behavior patterns
        """
        self.brain_graph = brain_graph
        self.model_path = model_path
        self.pattern_path = pattern_path
        
        # ML Model
        self._model = RandomForestClassifier(n_estimators=100, random_state=42)
        self._label_encoder = LabelEncoder()
        self._features_encoded = False
        
        # Behavior patterns
        self._action_patterns: Dict[str, List[UserAction]] = defaultdict(list)
        self._context_patterns: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        
        # Recent actions for prediction
        self._recent_actions: List[UserAction] = []
        self._max_recent_actions = 50
        
        # Prediction cache
        self._prediction_cache: Dict[str, Prediction] = {}
        self._cache_ttl = 300  # 5 minutes
        
        # Load existing patterns
        self._load_patterns()
    
    def record_action(self, action: UserAction) -> None:
        """Record a user action for learning.
        
        Args:
            action: User action to record
        """
        self._action_patterns[action.action].append(action)
        self._recent_actions.append(action)
        
        # Update recent actions list
        if len(self._recent_actions) > self._max_recent_actions:
            self._recent_actions.pop(0)
        
        # Update context patterns
        for key, value in action.context.items():
            self._context_patterns[action.action][f"{key}={value}"] += 1
        
        _LOGGER.debug(f"Recorded action: {action.action}")
    
    def predict_next_action(
        self,
        current_context: Dict[str, Any],
        recent_actions: Optional[List[str]] = None
    ) -> List[Prediction]:
        """Predict the next likely user actions.
        
        Args:
            current_context: Current home state context
            recent_actions: List of recently executed actions
            
        Returns:
            List of predictions sorted by confidence
        """
        cache_key = self._generate_cache_key(current_context, recent_actions)
        
        # Check cache
        if cache_key in self._prediction_cache:
            cached = self._prediction_cache[cache_key]
            if time.time() - cached.timestamp.timestamp() < self._cache_ttl:
                return [cached]
        
        # Get potential actions
        potential_actions = self._get_potential_actions(current_context, recent_actions)
        
        # Score and rank actions
        predictions = []
        for action, score in potential_actions:
            prediction = self._create_prediction(action, score, current_context)
            predictions.append(prediction)
        
        # Sort by confidence
        predictions.sort(key=lambda p: p.confidence, reverse=True)
        
        # Update cache
        if predictions:
            self._prediction_cache[cache_key] = predictions[0]
        
        return predictions
    
    def _get_potential_actions(
        self,
        context: Dict[str, Any],
        recent_actions: Optional[List[str]]
    ) -> List:
        """Get potential actions with scores.
        
        Args:
            context: Current context
            recent_actions: Recent actions
            
        Returns:
            List of (action, score) tuples
        """
        scores: Dict[str, float] = defaultdict(float)
        
        # Score based on recent actions
        if recent_actions:
            for action in recent_actions:
                if action in self._action_patterns:
                    scores[action] += 2.0
        
        # Score based on context patterns
        for action, context_scores in self._context_patterns.items():
            for ctx_key, ctx_val in context.items():
                key = f"{ctx_key}={ctx_val}"
                if key in context_scores:
                    scores[action] += context_scores[key] * 0.5
        
        # Score based on historical patterns
        for action, actions_list in self._action_patterns.items():
            # Weight recent actions more
            for i, action_record in enumerate(actions_list[-20:]):
                weight = (i + 1) / len(actions_list[-20:])
                scores[action] += weight * 0.1
        
        # Convert to sorted list
        action_list = list(scores.items())
        action_list.sort(key=lambda x: x[1], reverse=True)
        
        return action_list[:10]  # Top 10 actions
    
    def _create_prediction(
        self,
        action: str,
        confidence: float,
        context: Dict[str, Any]
    ) -> Prediction:
        """Create a prediction object.
        
        Args:
            action: Predicted action
            confidence: Prediction confidence
            context: Current context
            
        Returns:
            Prediction object
        """
        # Generate suggested automation
        automation = self._generate_automation_suggestion(action, context)
        
        return Prediction(
            predicted_action=action,
            confidence=min(confidence, 1.0),
            suggested_automation=automation,
            timestamp=datetime.now()
        )
    
    def _generate_automation_suggestion(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate an automation suggestion for a predicted action.
        
        Args:
            action: Predicted action
            context: Current context
            
        Returns:
            Automation suggestion dictionary
        """
        suggestion = {
            "action": action,
            "trigger": "predicted",
            "conditions": [],
            "actions": [],
            "suggested_by": "predictive_automation",
            "confidence_threshold": 0.7
        }
        
        # Add conditions based on context
        for key, value in context.items():
            if key in ["time_of_day", "day_of_week", "presence", "weather"]:
                suggestion["conditions"].append({
                    "type": "state",
                    "entity": f"input_{key}" if key != "presence" else "binary_sensor.presence",
                    "state": str(value)
                })
        
        # Add automation action
        suggestion["actions"].append({
            "action": f"automation.{action}",
            "enabled": True
        })
        
        return suggestion
    
    def _generate_cache_key(
        self,
        context: Dict[str, Any],
        recent_actions: Optional[List[str]]
    ) -> str:
        """Generate cache key for predictions.
        
        Args:
            context: Current context
            recent_actions: Recent actions
            
        Returns:
            Cache key string
        """
        context_str = ",".join(f"{k}={v}" for k, v in sorted(context.items()))
        actions_str = ",".join(recent_actions or [])
        return f"{context_str}|{actions_str}"
    
    def train_from_history(self, actions: List[UserAction]) -> None:
        """Train the prediction model from historical data.
        
        Args:
            actions: Historical user actions
        """
        if not actions:
            return
        
        # Prepare training data
        X = []
        y = []
        
        for action in actions:
            features = self._extract_features(action)
            X.append(features)
            y.append(action.action)
        
        if not X:
            return
        
        # Encode labels
        y_encoded = self._label_encoder.fit_transform(y)
        
        # Train model
        self._model.fit(X, y_encoded)
        self._features_encoded = True
        
        _LOGGER.info(f"Trained model with {len(actions)} samples")
    
    def _extract_features(self, action: UserAction) -> List[float]:
        """Extract features from a user action.
        
        Args:
            action: User action
            
        Returns:
            List of feature values
        """
        features = []
        
        # Time-based features
        features.append(action.timestamp.hour / 24.0)
        features.append(action.timestamp.weekday() / 7.0)
        features.append(action.timestamp.month / 12.0)
        
        # Entity count
        features.append(len(action.entities) / 10.0)
        
        # Context features (encoded as floats)
        for key in ["presence", "weather", "time_of_day"]:
            if key in action.context:
                features.append(hash(action.context[key]) % 100 / 100.0)
            else:
                features.append(0.0)
        
        return features
    
    def get_automation_suggestions(self, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Get automation suggestions based on learned patterns.
        
        Args:
            threshold: Confidence threshold
            
        Returns:
            List of automation suggestions
        """
        suggestions = []
        
        for action, actions_list in self._action_patterns.items():
            if len(actions_list) >= 5:  # Minimum occurrences
                # Calculate confidence
                confidence = len(actions_list) / 100.0
                
                if confidence >= threshold:
                    suggestion = {
                        "action": action,
                        "confidence": confidence,
                        "occurrences": len(actions_list),
                        "suggested_by": "pattern_analysis"
                    }
                    suggestions.append(suggestion)
        
        suggestions.sort(key=lambda s: s["confidence"], reverse=True)
        return suggestions
    
    def _load_patterns(self) -> None:
        """Load existing patterns from disk."""
        try:
            import os
            if os.path.exists(self.pattern_path):
                with open(self.pattern_path, "rb") as f:
                    data = pickle.load(f)
                    self._action_patterns = data.get("_action_patterns", defaultdict(list))
                    self._context_patterns = data.get("_context_patterns", defaultdict(lambda: defaultdict(float)))
                    _LOGGER.info(f"Loaded patterns from {self.pattern_path}")
        except Exception as e:
            _LOGGER.warning(f"Failed to load patterns: {e}")
    
    def save_patterns(self) -> None:
        """Save patterns to disk."""
        try:
            data = {
                "_action_patterns": dict(self._action_patterns),
                "_context_patterns": dict(self._context_patterns)
            }
            with open(self.pattern_path, "wb") as f:
                pickle.dump(data, f)
            _LOGGER.info(f"Saved patterns to {self.pattern_path}")
        except Exception as e:
            _LOGGER.warning(f"Failed to save patterns: {e}")
