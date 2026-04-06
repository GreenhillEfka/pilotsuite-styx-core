"""Rule Optimizer — Auto-tuning for Symbiotic Rules.
Scores, ranks, and optimizes existing rules based on execution history.
"""
import logging
from typing import Dict, List
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

@dataclass
class RuleScore:
    rule_id: str
    score: float
    execution_count: int
    false_positive_rate: float
    utility_score: float

class RuleOptimizer:
    def __init__(self, rule_engine):
        self.rule_engine = rule_engine
        self.execution_history: List[dict] = []
        self.user_feedback: Dict[str, bool] = {}  # rule_id -> was_useful
    
    def record_execution(self, rule_id: str, context: dict, action_taken: dict):
        self.execution_history.append({
            "rule_id": rule_id,
            "context": context,
            "action": action_taken,
            "timestamp": "now"
        })
        # Keep last 500 executions
        if len(self.execution_history) > 500:
            self.execution_history = self.execution_history[-500:]
    
    def record_feedback(self, rule_id: str, was_useful: bool):
        self.user_feedback[rule_id] = was_useful
        _LOGGER.info(f"Feedback recorded for {rule_id}: {was_useful}")
    
    def score_all_rules(self) -> List[RuleScore]:
        """Score all rules based on execution history and feedback."""
        scores = []
        
        for rule_id, rule in self.rule_engine.rules.items():
            exec_count = rule.get("triggered_count", 0)
            
            # Calculate false positive rate (rules triggered but action not useful)
            fp_count = sum(1 for e in self.execution_history 
                          if e["rule_id"] == rule_id and not self.user_feedback.get(rule_id, True))
            fp_rate = fp_count / max(exec_count, 1)
            
            # Utility score based on feedback
            utility = 1.0 if self.user_feedback.get(rule_id, True) else 0.5
            
            # Combined score
            score = (utility * 0.6) + ((1 - fp_rate) * 0.3) + (min(exec_count / 10, 1) * 0.1)
            
            scores.append(RuleScore(
                rule_id=rule_id,
                score=round(score, 3),
                execution_count=exec_count,
                false_positive_rate=round(fp_rate, 3),
                utility_score=round(utility, 3)
            ))
        
        return sorted(scores, key=lambda s: s.score, reverse=True)
    
    def get_optimization_suggestions(self) -> List[dict]:
        """Get suggestions for rule optimization."""
        suggestions = []
        scores = self.score_all_rules()
        
        for score in scores:
            if score.score < 0.5:
                suggestions.append({
                    "rule_id": score.rule_id,
                    "issue": "low_score",
                    "suggestion": "Consider disabling or adjusting condition",
                    "current_score": score.score
                })
            if score.false_positive_rate > 0.3:
                suggestions.append({
                    "rule_id": score.rule_id,
                    "issue": "high_false_positive",
                    "suggestion": "Add more specific conditions",
                    "fp_rate": score.false_positive_rate
                })
            if score.execution_count == 0:
                suggestions.append({
                    "rule_id": score.rule_id,
                    "issue": "never_triggered",
                    "suggestion": "Review condition or remove rule",
                    "age_days": 7
                })
        
        return suggestions
    
    def auto_disable_low_score_rules(self, threshold: float = 0.3):
        """Automatically disable rules with very low scores."""
        scores = self.score_all_rules()
        disabled = 0
        
        for score in scores:
            if score.score < threshold:
                self.rule_engine.disable_rule(score.rule_id)
                disabled += 1
                _LOGGER.info(f"Auto-disabled low-score rule: {score.rule_id} (score: {score.score})")
        
        return disabled
