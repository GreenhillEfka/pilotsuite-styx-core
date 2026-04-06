"""Learning Memory Sync — Persistent Pattern Storage.
Bridges learned patterns between Core and persistent storage.
"""
import logging
import json
from typing import Dict, List
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

class LearningMemorySync:
    def __init__(self, storage_path: str = "/tmp/pilotsuite_memory"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.patterns_file = self.storage_path / "patterns.json"
        self.feedback_file = self.storage_path / "feedback.json"
    
    def save_patterns(self, patterns: List[dict]):
        """Save patterns to persistent storage."""
        try:
            existing = self.load_patterns()
            existing.extend(patterns)
            
            # Deduplicate by pattern_id
            seen = set()
            unique = []
            for p in existing:
                pid = p.get("pattern_id")
                if pid not in seen:
                    seen.add(pid)
                    unique.append(p)
            
            with open(self.patterns_file, 'w') as f:
                json.dump(unique, f, indent=2)
            
            _LOGGER.info(f"Saved {len(unique)} patterns to {self.patterns_file}")
        except Exception as e:
            _LOGGER.error(f"Failed to save patterns: {e}")
    
    def load_patterns(self) -> List[dict]:
        """Load patterns from persistent storage."""
        if self.patterns_file.exists():
            try:
                with open(self.patterns_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                _LOGGER.error(f"Failed to load patterns: {e}")
        return []
    
    def save_feedback(self, feedback: Dict[str, bool]):
        """Save user feedback to persistent storage."""
        try:
            existing = self.load_feedback()
            existing.update(feedback)
            
            with open(self.feedback_file, 'w') as f:
                json.dump(existing, f, indent=2)
            
            _LOGGER.info(f"Saved feedback for {len(feedback)} rules")
        except Exception as e:
            _LOGGER.error(f"Failed to save feedback: {e}")
    
    def load_feedback(self) -> Dict[str, bool]:
        """Load feedback from persistent storage."""
        if self.feedback_file.exists():
            try:
                with open(self.feedback_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                _LOGGER.error(f"Failed to load feedback: {e}")
        return {}
    
    def get_pattern_history(self, pattern_id: str) -> List[dict]:
        """Get history for a specific pattern."""
        patterns = self.load_patterns()
        return [p for p in patterns if p.get("pattern_id") == pattern_id]
    
    def get_stats(self) -> dict:
        patterns = self.load_patterns()
        feedback = self.load_feedback()
        
        return {
            "total_patterns": len(patterns),
            "total_feedback": len(feedback),
            "positive_feedback": sum(1 for v in feedback.values() if v),
            "negative_feedback": sum(1 for v in feedback.values() if not v),
            "storage_path": str(self.storage_path)
        }
