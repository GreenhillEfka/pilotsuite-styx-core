"""P3-002: Habit Learning System — Reinforcement Learning, Feedback Loop."""
from __future__ import annotations

import logging
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class HabitStrength(Enum):
    """Habit strength levels."""
    WEAK = "weak"  # <30% consistency
    MODERATE = "moderate"  # 30-60% consistency
    STRONG = "strong"  # 60-90% consistency
    ESTABLISHED = "established"  # >90% consistency


@dataclass
class Habit:
    """A learned habit pattern."""
    id: str
    name: str
    trigger: str
    action: str
    context: Dict[str, Any]
    strength: HabitStrength
    consistency: float  # 0.0 to 1.0
    executions: int = 0
    last_executed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    reward_history: List[float] = field(default_factory=list)


@dataclass
class Feedback:
    """User feedback on habit execution."""
    habit_id: str
    timestamp: float
    rating: float  # -1.0 to 1.0
    comment: Optional[str] = None


class HabitLearningSystem:
    """Learns and adapts habits based on user feedback."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._habits: Dict[str, Habit] = {}
        self._feedback: List[Feedback] = []
        self._execution_log: List[Dict[str, Any]] = []
        
        self._load_habits()

    def create_habit(
        self,
        name: str,
        trigger: str,
        action: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new habit to track."""
        import hashlib
        habit_id = hashlib.sha256(f"{name}{trigger}{time.time()}".encode()).hexdigest()[:16]
        
        habit = Habit(
            id=habit_id,
            name=name,
            trigger=trigger,
            action=action,
            context=context or {},
            strength=HabitStrength.WEAK,
            consistency=0.0
        )
        
        self._habits[habit_id] = habit
        self._save_habits()
        
        logger.info(f"Created habit: {name} ({habit_id})")
        return habit_id

    def execute_habit(self, habit_id: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Execute a habit and log it."""
        if habit_id not in self._habits:
            return False
        
        habit = self._habits[habit_id]
        habit.executions += 1
        habit.last_executed = time.time()
        
        # Log execution
        self._execution_log.append({
            "habit_id": habit_id,
            "timestamp": time.time(),
            "context": context or {}
        })
        
        # Update consistency
        self._update_consistency(habit)
        
        self._save_habits()
        return True

    def submit_feedback(self, habit_id: str, rating: float, comment: Optional[str] = None):
        """Submit user feedback for habit."""
        feedback = Feedback(
            habit_id=habit_id,
            timestamp=time.time(),
            rating=max(-1.0, min(1.0, rating)),  # Clamp to [-1, 1]
            comment=comment
        )
        
        self._feedback.append(feedback)
        
        # Update habit reward history
        if habit_id in self._habits:
            habit = self._habits[habit_id]
            habit.reward_history.append(rating)
            # Keep last 100 ratings
            habit.reward_history = habit.reward_history[-100:]
        
        self._save_habits()
        logger.debug(f"Feedback for {habit_id}: {rating}")

    def _update_consistency(self, habit: Habit):
        """Update habit consistency score."""
        if habit.executions < 5:
            habit.consistency = habit.executions / 5.0 * 0.5
        else:
            # Calculate based on execution frequency
            now = time.time()
            age_days = (now - habit.created_at) / (24 * 3600)
            expected_executions = age_days  # Assume daily habit
            habit.consistency = min(1.0, habit.executions / max(1, expected_executions))
        
        # Update strength
        if habit.consistency < 0.3:
            habit.strength = HabitStrength.WEAK
        elif habit.consistency < 0.6:
            habit.strength = HabitStrength.MODERATE
        elif habit.consistency < 0.9:
            habit.strength = HabitStrength.STRONG
        else:
            habit.strength = HabitStrength.ESTABLISHED

    def get_habit_suggestions(self, context: Dict[str, Any]) -> List[Habit]:
        """Get habit suggestions based on context."""
        suggestions = []
        
        for habit in self._habits.values():
            # Match context
            score = self._match_context(habit, context)
            
            # Boost by strength
            strength_bonus = {
                HabitStrength.WEAK: 0.0,
                HabitStrength.MODERATE: 0.1,
                HabitStrength.STRONG: 0.2,
                HabitStrength.ESTABLISHED: 0.3,
            }
            
            final_score = score + strength_bonus.get(habit.strength, 0)
            
            if final_score > 0.5:
                suggestions.append((final_score, habit))
        
        # Sort by score
        suggestions.sort(key=lambda x: x[0], reverse=True)
        return [h for _, h in suggestions[:5]]

    def _match_context(self, habit: Habit, context: Dict[str, Any]) -> float:
        """Calculate context match score."""
        score = 0.0
        matches = 0
        
        for key, value in habit.context.items():
            if key in context:
                if context[key] == value:
                    matches += 1
                    score += 0.25
        
        return min(1.0, score)

    def get_habit(self, habit_id: str) -> Optional[Habit]:
        """Get habit by ID."""
        return self._habits.get(habit_id)

    def list_habits(self) -> List[Habit]:
        """List all habits."""
        return list(self._habits.values())

    def delete_habit(self, habit_id: str) -> bool:
        """Delete a habit."""
        if habit_id in self._habits:
            del self._habits[habit_id]
            self._save_habits()
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get learning statistics."""
        total_feedback = len(self._feedback)
        avg_rating = sum(f.rating for f in self._feedback) / max(1, total_feedback)
        
        strength_counts = {}
        for habit in self._habits.values():
            strength_counts[habit.strength.value] = strength_counts.get(habit.strength.value, 0) + 1
        
        return {
            "total_habits": len(self._habits),
            "total_executions": sum(h.executions for h in self._habits.values()),
            "total_feedback": total_feedback,
            "avg_feedback_rating": avg_rating,
            "strength_distribution": strength_counts,
        }

    def _save_habits(self):
        """Save habits to disk."""
        habits_file = self.data_dir / "habits.json"
        
        data = {}
        for habit_id, habit in self._habits.items():
            data[habit_id] = {
                "id": habit.id,
                "name": habit.name,
                "trigger": habit.trigger,
                "action": habit.action,
                "context": habit.context,
                "strength": habit.strength.value,
                "consistency": habit.consistency,
                "executions": habit.executions,
                "last_executed": habit.last_executed,
                "created_at": habit.created_at,
                "reward_history": habit.reward_history,
            }
        
        with open(habits_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_habits(self):
        """Load habits from disk."""
        habits_file = self.data_dir / "habits.json"
        
        if not habits_file.exists():
            return
        
        try:
            with open(habits_file, 'r') as f:
                data = json.load(f)
            
            for habit_id, habit_data in data.items():
                habit = Habit(
                    id=habit_data["id"],
                    name=habit_data["name"],
                    trigger=habit_data["trigger"],
                    action=habit_data["action"],
                    context=habit_data.get("context", {}),
                    strength=HabitStrength(habit_data["strength"]),
                    consistency=habit_data.get("consistency", 0.0),
                    executions=habit_data.get("executions", 0),
                    last_executed=habit_data.get("last_executed", 0),
                    created_at=habit_data.get("created_at", 0),
                    reward_history=habit_data.get("reward_history", []),
                )
                self._habits[habit_id] = habit
            
            logger.info(f"Loaded {len(self._habits)} habits")
        except Exception as e:
            logger.error(f"Failed to load habits: {e}")


# Global default habit system
default_habit_system: Optional[HabitLearningSystem] = None


def init_habit_system(data_dir: str) -> HabitLearningSystem:
    """Initialize global habit learning system."""
    global default_habit_system
    default_habit_system = HabitLearningSystem(data_dir)
    return default_habit_system
