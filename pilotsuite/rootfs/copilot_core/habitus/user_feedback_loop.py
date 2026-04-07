"""User Feedback Loop — Explizites Feedback für gelernte Patterns (SOTA 2026).

Feedback-Typen:
- 👍 Thumbs Up (accepted)
- 👎 Thumbs Down (rejected)
- ✏️ Correction (modified)
- 💬 Comment (text feedback)

Features:
1. Feedback Collection (UI + API)
2. Confidence Update (Bayesian)
3. Pattern Refinement
4. Feedback Analytics
5. Retention Tracking

Integration:
- Dashboard → Feedback Buttons
- Habitus → Confidence Update
- Analytics → Feedback Stats
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import threading
from collections import defaultdict, deque

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# FEEDBACK TYPES
# =============================================================================

class FeedbackType(str, Enum):
    """Feedback Typen."""
    
    THUMBS_UP = "thumbs_up"  # 👍 Accepted
    THUMBS_DOWN = "thumbs_down"  # 👎 Rejected
    CORRECTION = "correction"  # ✏️ Modified
    COMMENT = "comment"  # 💬 Text feedback


@dataclass
class UserFeedback:
    """User Feedback Entry."""
    
    feedback_id: str
    pattern_id: str
    feedback_type: FeedbackType
    user_id: str = "default"
    comment: Optional[str] = None
    correction_data: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "feedback_type": self.feedback_type.value,
        }


# =============================================================================
# FEEDBACK COLLECTOR
# =============================================================================

class UserFeedbackCollector:
    """Collector für User Feedback."""
    
    def __init__(self, habitus_service):
        self._habitus_service = habitus_service
        self._feedback_history: Dict[str, List[UserFeedback]] = defaultdict(list)  # pattern_id → feedbacks
        self._pattern_feedback: Dict[str, Dict[str, int]] = defaultdict(lambda: {"up": 0, "down": 0, "correction": 0})
        self._retention_history: deque = deque(maxlen=1000)
        self._feedback_hooks: List[Callable[[UserFeedback], None]] = []
        self._lock = threading.Lock()
        _LOGGER.info("UserFeedbackCollector initialized")
    
    def submit_feedback(
        self,
        pattern_id: str,
        feedback_type: FeedbackType,
        user_id: str = "default",
        comment: Optional[str] = None,
        correction_data: Optional[Dict[str, Any]] = None,
    ) -> UserFeedback:
        """Feedback einreichen."""
        # Get current confidence
        pattern = self._habitus_service.get_pattern(pattern_id)
        confidence_before = pattern.confidence if pattern else 0.5
        
        # Create feedback entry
        feedback = UserFeedback(
            feedback_id=f"fb_{pattern_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            pattern_id=pattern_id,
            feedback_type=feedback_type,
            user_id=user_id,
            comment=comment,
            correction_data=correction_data,
            confidence_before=confidence_before,
        )
        
        with self._lock:
            # Store feedback
            self._feedback_history[pattern_id].append(feedback)
            
            # Update counters
            if feedback_type == FeedbackType.THUMBS_UP:
                self._pattern_feedback[pattern_id]["up"] += 1
            elif feedback_type == FeedbackType.THUMBS_DOWN:
                self._pattern_feedback[pattern_id]["down"] += 1
            elif feedback_type == FeedbackType.CORRECTION:
                self._pattern_feedback[pattern_id]["correction"] += 1
            
            # Track retention
            self._retention_history.append({
                "pattern_id": pattern_id,
                "feedback_type": feedback_type.value,
                "timestamp": feedback.created_at,
            })
        
        # Update pattern confidence via HabitusService
        if feedback_type == FeedbackType.THUMBS_UP:
            self._habitus_service.process_feedback(pattern_id, "accepted", comment)
        elif feedback_type == FeedbackType.THUMBS_DOWN:
            self._habitus_service.process_feedback(pattern_id, "rejected", comment)
        elif feedback_type == FeedbackType.CORRECTION:
            self._habitus_service.process_feedback(
                pattern_id,
                "corrected",
                comment,
                correction_data,
            )
        
        # Get new confidence
        pattern = self._habitus_service.get_pattern(pattern_id)
        feedback.confidence_after = pattern.confidence if pattern else confidence_before
        
        # Notify hooks
        for hook in self._feedback_hooks:
            try:
                hook(feedback)
            except Exception as e:
                _LOGGER.error(f"Feedback hook error: {e}")
        
        _LOGGER.info(
            f"Feedback received: {feedback_type.value} for pattern {pattern_id} "
            f"(confidence: {confidence_before:.2f} → {feedback.confidence_after:.2f})"
        )
        
        return feedback
    
    def get_pattern_feedback(self, pattern_id: str) -> List[UserFeedback]:
        """Feedback für Pattern holen."""
        with self._lock:
            return list(self._feedback_history.get(pattern_id, []))
    
    def get_feedback_summary(self, pattern_id: str) -> Dict[str, Any]:
        """Feedback Summary für Pattern."""
        with self._lock:
            counts = self._pattern_feedback.get(pattern_id, {"up": 0, "down": 0, "correction": 0})
            feedbacks = self._feedback_history.get(pattern_id, [])
            
            # Calculate acceptance rate
            total = counts["up"] + counts["down"]
            acceptance_rate = counts["up"] / max(total, 1)
            
            # Get confidence trend
            if len(feedbacks) >= 2:
                confidence_trend = feedbacks[-1].confidence_after - feedbacks[0].confidence_before
            else:
                confidence_trend = 0.0
            
            return {
                "pattern_id": pattern_id,
                "thumbs_up": counts["up"],
                "thumbs_down": counts["down"],
                "corrections": counts["correction"],
                "total_feedback": total + counts["correction"],
                "acceptance_rate": round(acceptance_rate * 100, 1),
                "confidence_trend": round(confidence_trend, 3),
                "recent_feedback": [f.to_dict() for f in feedbacks[-5:]],
            }
    
    def get_all_feedback_stats(self) -> Dict[str, Any]:
        """Gesamt-Feedback-Statistiken."""
        with self._lock:
            total_up = sum(c["up"] for c in self._pattern_feedback.values())
            total_down = sum(c["down"] for c in self._pattern_feedback.values())
            total_correction = sum(c["correction"] for c in self._pattern_feedback.values())
            
            total = total_up + total_down
            overall_acceptance = total_up / max(total, 1)
            
            return {
                "total_patterns_with_feedback": len(self._pattern_feedback),
                "total_feedback": total_up + total_down + total_correction,
                "thumbs_up": total_up,
                "thumbs_down": total_down,
                "corrections": total_correction,
                "overall_acceptance_rate": round(overall_acceptance * 100, 1),
                "feedback_retention": len(self._retention_history),
            }
    
    def register_feedback_hook(self, hook: Callable[[UserFeedback], None]) -> None:
        """Hook für neues Feedback."""
        self._feedback_hooks.append(hook)
    
    def get_retention_data(self, days: int = 7) -> List[Dict[str, Any]]:
        """Retention-Daten für Dashboard."""
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            return [
                entry for entry in self._retention_history
                if datetime.fromisoformat(entry["timestamp"]).replace(tzinfo=timezone.utc) > cutoff
            ]


# =============================================================================
# FEEDBACK UI COMPONENTS
# =============================================================================

def get_feedback_card_config(pattern_id: str, summary: Dict[str, Any]) -> Dict[str, Any]:
    """Lovelace Card Config für Feedback."""
    return {
        "type": "custom:pattern-feedback-card",
        "title": "Pattern Feedback",
        "pattern_id": pattern_id,
        "stats": {
            "thumbs_up": summary.get("thumbs_up", 0),
            "thumbs_down": summary.get("thumbs_down", 0),
            "corrections": summary.get("corrections", 0),
            "acceptance_rate": summary.get("acceptance_rate", 0),
        },
        "buttons": [
            {
                "icon": "mdi:thumb-up",
                "action": "thumbs_up",
                "tooltip": "This pattern is helpful",
            },
            {
                "icon": "mdi:thumb-down",
                "action": "thumbs_down",
                "tooltip": "This pattern is not helpful",
            },
            {
                "icon": "mdi:pencil",
                "action": "correction",
                "tooltip": "Suggest a correction",
            },
        ],
        "recent_feedback": summary.get("recent_feedback", []),
    }


# =============================================================================
# Singleton Factory
# =============================================================================

_collectors: Dict[str, UserFeedbackCollector] = {}


def get_user_feedback_collector(habitus_service) -> UserFeedbackCollector:
    """Singleton-Zugriff."""
    key = "default"
    
    if key not in _collectors:
        _collectors[key] = UserFeedbackCollector(habitus_service)
    
    return _collectors[key]
