"""Habitus Workflow — Complete Pipeline: Erfassung → Verarbeitung → Darstellung.

Workflow:
1. Event Collection — HA Events sammeln
2. Pattern Mining — Muster erkennen
3. Confidence Calculation — Wilson + Bayesian
4. Storage — Im UnifiedHabitusStore
5. Visualization — Dashboard Cards
6. User Feedback — Accept/Reject/Correct
7. Learning — Confidence Update

SOTA 2026:
- Real-time Mining
- Adaptive Confidence
- Interactive Visualization
- Feedback Loop
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import threading
from collections import defaultdict

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# WORKFLOW STATES
# =============================================================================

class HabitusWorkflowState(str, Enum):
    """Workflow State."""
    
    COLLECTING = "collecting"
    MINING = "mining"
    VALIDATING = "validating"
    STORING = "storing"
    VISUALIZING = "visualizing"
    WAITING_FEEDBACK = "waiting_feedback"
    LEARNING = "learning"


@dataclass
class HabitusWorkflowStep:
    """Einzelner Workflow Step."""
    
    step_name: str
    state: HabitusWorkflowState
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HabitusWorkflowInstance:
    """Instanz eines Workflows."""
    
    workflow_id: str
    zone_id: str
    event_type: str
    steps: List[HabitusWorkflowStep] = field(default_factory=list)
    current_step: int = 0
    pattern_id: Optional[str] = None
    confidence: float = 0.0
    user_feedback: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "zone_id": self.zone_id,
            "event_type": self.event_type,
            "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step,
            "pattern_id": self.pattern_id,
            "confidence": round(self.confidence, 3),
            "user_feedback": self.user_feedback,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "status": "completed" if self.completed_at else "in_progress",
        }


# =============================================================================
# HABITUS WORKFLOW ENGINE
# =============================================================================

class HabitusWorkflowEngine:
    """Engine für Habitus Workflows."""
    
    def __init__(self, habitus_store, habitus_service):
        self._habitus_store = habitus_store
        self._habitus_service = habitus_service
        self._workflows: Dict[str, HabitusWorkflowInstance] = {}
        self._active_workflows: Dict[str, str] = {}  # zone_id → workflow_id
        self._completion_hooks: List[Callable[[HabitusWorkflowInstance], None]] = []
        self._lock = threading.Lock()
        _LOGGER.info("HabitusWorkflowEngine initialized")
    
    def start_workflow(self, zone_id: str, event_type: str, context: Dict[str, Any]) -> str:
        """Workflow starten."""
        workflow_id = f"wf_{zone_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        workflow = HabitusWorkflowInstance(
            workflow_id=workflow_id,
            zone_id=zone_id,
            event_type=event_type,
        )
        
        # Step 1: Event Collection
        workflow.steps.append(HabitusWorkflowStep(
            step_name="event_collection",
            state=HabitusWorkflowState.COLLECTING,
            result={"context": context},
        ))
        
        with self._lock:
            self._workflows[workflow_id] = workflow
            self._active_workflows[zone_id] = workflow_id
        
        _LOGGER.info(f"Started workflow {workflow_id} for zone {zone_id}")
        
        return workflow_id
    
    def mine_pattern(self, workflow_id: str, trigger: Dict[str, Any], action: Dict[str, Any]) -> Optional[str]:
        """Pattern minen (Step 2)."""
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                return None
            
            # Complete previous step
            if workflow.steps:
                workflow.steps[-1].completed_at = datetime.now(timezone.utc).isoformat()
                workflow.steps[-1].state = HabitusWorkflowState.MINING
            
            # Step 2: Pattern Mining
            workflow.steps.append(HabitusWorkflowStep(
                step_name="pattern_mining",
                state=HabitusWorkflowState.MINING,
            ))
            workflow.current_step = len(workflow.steps) - 1
        
        # Mine pattern
        pattern_id = self._habitus_service.observe(
            trigger=trigger,
            action=action,
            zone=workflow.zone_id,
            context={"workflow_id": workflow_id},
        )
        
        with self._lock:
            workflow.pattern_id = pattern_id
            workflow.steps[-1].completed_at = datetime.now(timezone.utc).isoformat()
            workflow.steps[-1].result = {"pattern_id": pattern_id}
        
        _LOGGER.info(f"Mined pattern {pattern_id} in workflow {workflow_id}")
        
        return pattern_id
    
    def calculate_confidence(self, workflow_id: str) -> float:
        """Confidence berechnen (Step 3)."""
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow or not workflow.pattern_id:
                return 0.0
            
            # Complete previous step
            if workflow.steps:
                workflow.steps[-1].completed_at = datetime.now(timezone.utc).isoformat()
            
            # Step 3: Confidence Calculation
            workflow.steps.append(HabitusWorkflowStep(
                step_name="confidence_calculation",
                state=HabitusWorkflowState.VALIDATING,
            ))
            workflow.current_step = len(workflow.steps) - 1
        
        # Get pattern confidence
        pattern = self._habitus_store.get_pattern(workflow.pattern_id)
        if pattern:
            confidence = pattern.confidence
        else:
            confidence = 0.5
        
        with self._lock:
            workflow.confidence = confidence
            workflow.steps[-1].completed_at = datetime.now(timezone.utc).isoformat()
            workflow.steps[-1].result = {"confidence": confidence}
        
        return confidence
    
    def store_pattern(self, workflow_id: str) -> bool:
        """Pattern speichern (Step 4)."""
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                return False
            
            # Complete previous step
            if workflow.steps:
                workflow.steps[-1].completed_at = datetime.now(timezone.utc).isoformat()
            
            # Step 4: Storage
            workflow.steps.append(HabitusWorkflowStep(
                step_name="storage",
                state=HabitusWorkflowState.STORING,
            ))
            workflow.current_step = len(workflow.steps) - 1
        
        # Pattern is already stored in mine_pattern, just mark as complete
        with self._lock:
            workflow.steps[-1].completed_at = datetime.now(timezone.utc).isoformat()
            workflow.steps[-1].result = {"stored": True}
        
        return True
    
    def visualize(self, workflow_id: str) -> Dict[str, Any]:
        """Visualisierung erstellen (Step 5)."""
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                return {}
            
            # Complete previous step
            if workflow.steps:
                workflow.steps[-1].completed_at = datetime.now(timezone.utc).isoformat()
            
            # Step 5: Visualization
            workflow.steps.append(HabitusWorkflowStep(
                step_name="visualization",
                state=HabitusWorkflowState.VISUALIZING,
            ))
            workflow.current_step = len(workflow.steps) - 1
        
        visualization = {
            "workflow_id": workflow.workflow_id,
            "zone_id": workflow.zone_id,
            "pattern_id": workflow.pattern_id,
            "confidence": workflow.confidence,
            "steps_completed": len([s for s in workflow.steps if s.completed_at]),
            "total_steps": len(workflow.steps),
        }
        
        with self._lock:
            workflow.steps[-1].completed_at = datetime.now(timezone.utc).isoformat()
            workflow.steps[-1].result = visualization
        
        return visualization
    
    def submit_feedback(self, workflow_id: str, feedback_type: str) -> bool:
        """User Feedback einreichen (Step 6)."""
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                return False
            
            # Complete previous step
            if workflow.steps:
                workflow.steps[-1].completed_at = datetime.now(timezone.utc).isoformat()
            
            # Step 6: Feedback
            workflow.steps.append(HabitusWorkflowStep(
                step_name="feedback",
                state=HabitusWorkflowState.WAITING_FEEDBACK,
                result={"feedback_type": feedback_type},
            ))
            workflow.current_step = len(workflow.steps) - 1
            workflow.user_feedback = feedback_type
        
        # Process feedback
        if workflow.pattern_id:
            self._habitus_service.process_feedback(
                pattern_id=workflow.pattern_id,
                feedback_type=feedback_type,
            )
        
        with self._lock:
            workflow.steps[-1].completed_at = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def complete_learning(self, workflow_id: str) -> bool:
        """Learning abschließen (Step 7)."""
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                return False
            
            # Complete previous step
            if workflow.steps:
                workflow.steps[-1].completed_at = datetime.now(timezone.utc).isoformat()
            
            # Step 7: Learning
            workflow.steps.append(HabitusWorkflowStep(
                step_name="learning",
                state=HabitusWorkflowState.LEARNING,
            ))
            workflow.current_step = len(workflow.steps) - 1
        
        # Update confidence based on feedback
        if workflow.pattern_id and workflow.user_feedback:
            if workflow.user_feedback == "accepted":
                workflow.confidence = min(workflow.confidence + 0.1, 1.0)
            elif workflow.user_feedback == "rejected":
                workflow.confidence = max(workflow.confidence - 0.2, 0.0)
        
        # Complete workflow
        workflow.completed_at = datetime.now(timezone.utc).isoformat()
        
        with self._lock:
            workflow.steps[-1].completed_at = datetime.now(timezone.utc).isoformat()
            workflow.steps[-1].result = {
                "final_confidence": workflow.confidence,
                "learned": True,
            }
            
            # Remove from active
            if workflow.zone_id in self._active_workflows:
                del self._active_workflows[workflow.zone_id]
            
            # Notify completion hooks
            for hook in self._completion_hooks:
                try:
                    hook(workflow)
                except Exception as e:
                    _LOGGER.error(f"Completion hook error: {e}")
        
        _LOGGER.info(f"Completed workflow {workflow_id} with confidence {workflow.confidence}")
        
        return True
    
    def register_completion_hook(self, hook: Callable[[HabitusWorkflowInstance], None]) -> None:
        """Hook für Workflow Completion."""
        self._completion_hooks.append(hook)
    
    def get_workflow(self, workflow_id: str) -> Optional[HabitusWorkflowInstance]:
        """Workflow holen."""
        with self._lock:
            return self._workflows.get(workflow_id)
    
    def get_active_workflows(self) -> List[HabitusWorkflowInstance]:
        """Aktive Workflows."""
        with self._lock:
            return [
                self._workflows[wf_id]
                for wf_id in self._active_workflows.values()
            ]
    
    def get_workflow_stats(self) -> Dict[str, Any]:
        """Workflow Statistiken."""
        with self._lock:
            completed = sum(1 for w in self._workflows.values() if w.completed_at)
            feedback_received = sum(1 for w in self._workflows.values() if w.user_feedback)
            
            return {
                "total_workflows": len(self._workflows),
                "active_workflows": len(self._active_workflows),
                "completed_workflows": completed,
                "feedback_received": feedback_received,
                "avg_confidence": sum(w.confidence for w in self._workflows.values()) / max(len(self._workflows), 1),
                "feedback_rate": feedback_received / max(completed, 1),
            }


# =============================================================================
# Singleton Factory
# =============================================================================

_workflow_engines: Dict[str, HabitusWorkflowEngine] = {}


def get_habitus_workflow_engine(habitus_store, habitus_service) -> HabitusWorkflowEngine:
    """Workflow Engine holen/erstellen."""
    key = "default"
    
    if key not in _workflow_engines:
        _workflow_engines[key] = HabitusWorkflowEngine(habitus_store, habitus_service)
    
    return _workflow_engines[key]
