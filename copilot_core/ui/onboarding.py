"""P6-007: Onboarding Flow — Wizard, Tutorials, Sample Configs."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class OnboardingStep:
    """Single onboarding step."""
    id: str
    title: str
    description: str
    step_type: str  # intro, config, tutorial, complete
    component: str
    required: bool = True
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OnboardingProgress:
    """User onboarding progress."""
    user_id: str
    current_step: str
    completed_steps: List[str] = field(default_factory=list)
    started_at: float = field(default_factory=lambda: 0.0)
    completed_at: Optional[float] = None
    skipped_steps: List[str] = field(default_factory=list)


class OnboardingWizard:
    """Guided onboarding wizard."""

    def __init__(self):
        self._steps: Dict[str, OnboardingStep] = {}
        self._progress: Dict[str, OnboardingProgress] = {}
        self._completion_callbacks: List[Callable] = []
        self._register_default_steps()

    def _register_default_steps(self):
        """Register default onboarding steps."""
        self._steps["welcome"] = OnboardingStep(
            id="welcome",
            title="Welcome to PilotSuite",
            description="Your AI-powered smart home assistant",
            step_type="intro",
            component="WelcomeScreen",
            required=True,
            data={"image": "/onboarding/welcome.svg"}
        )
        
        self._steps["connect_hub"] = OnboardingStep(
            id="connect_hub",
            title="Connect Your Hub",
            description="Link PilotSuite to your Home Assistant",
            step_type="config",
            component="HubConnection",
            required=True,
            data={"fields": ["url", "token"]}
        )
        
        self._steps["setup_zones"] = OnboardingStep(
            id="setup_zones",
            title="Setup Zones",
            description="Define zones in your home",
            step_type="config",
            component="ZoneSetup",
            required=True,
            data={"min_zones": 1, "suggested": ["Living Room", "Bedroom", "Kitchen"]}
        )
        
        self._steps["voice_setup"] = OnboardingStep(
            id="voice_setup",
            title="Voice Control",
            description="Enable voice commands",
            step_type="config",
            component="VoiceSetup",
            required=False,
            data={"options": ["Whisper STT", "Piper TTS"]}
        )
        
        self._steps["habits_intro"] = OnboardingStep(
            id="habits_intro",
            title="Learn Your Habits",
            description="PilotSuite learns your routines automatically",
            step_type="tutorial",
            component="HabitsIntro",
            required=False,
            data={"features": ["Pattern Detection", "Predictive Automation"]}
        )
        
        self._steps["notifications"] = OnboardingStep(
            id="notifications",
            title="Notifications",
            description="Choose how you want to be notified",
            step_type="config",
            component="NotificationSetup",
            required=True,
            data={"channels": ["push", "email", "telegram"]}
        )
        
        self._steps["complete"] = OnboardingStep(
            id="complete",
            title="All Set!",
            description="You're ready to start using PilotSuite",
            step_type="complete",
            component="CompletionScreen",
            required=True,
            data={"next_steps": ["Explore Dashboard", "Try Voice Command", "View Tutorials"]}
        )

    def start_onboarding(self, user_id: str) -> OnboardingProgress:
        """Start onboarding for a user."""
        import time
        progress = OnboardingProgress(
            user_id=user_id,
            current_step="welcome",
            started_at=time.time()
        )
        self._progress[user_id] = progress
        logger.info(f"Started onboarding for user: {user_id}")
        return progress

    def complete_step(self, user_id: str, step_id: str, data: Optional[Dict] = None) -> bool:
        """Mark a step as completed."""
        if user_id not in self._progress:
            return False
        
        progress = self._progress[user_id]
        
        if step_id not in self._steps:
            return False
        
        # Validate step order
        if step_id != progress.current_step:
            return False
        
        # Mark complete
        progress.completed_steps.append(step_id)
        
        # Move to next step
        next_step = self._get_next_step(step_id)
        if next_step:
            progress.current_step = next_step
        else:
            # Onboarding complete
            import time
            progress.completed_at = time.time()
            self._trigger_completion(progress)
        
        logger.info(f"User {user_id} completed step: {step_id}")
        return True

    def skip_step(self, user_id: str, step_id: str) -> bool:
        """Skip a step."""
        if user_id not in self._progress:
            return False
        
        progress = self._progress[user_id]
        
        if step_id not in self._steps:
            return False
        
        if not self._steps[step_id].required:
            progress.skipped_steps.append(step_id)
            progress.current_step = self._get_next_step(step_id) or "complete"
            logger.info(f"User {user_id} skipped step: {step_id}")
            return True
        
        return False

    def _get_next_step(self, current_step_id: str) -> Optional[str]:
        """Get next step ID."""
        step_order = list(self._steps.keys())
        
        try:
            current_index = step_order.index(current_step_id)
            if current_index < len(step_order) - 1:
                return step_order[current_index + 1]
        except ValueError:
            pass
        
        return None

    def get_progress(self, user_id: str) -> Optional[OnboardingProgress]:
        """Get user onboarding progress."""
        return self._progress.get(user_id)

    def get_current_step(self, user_id: str) -> Optional[OnboardingStep]:
        """Get current step for user."""
        progress = self._progress.get(user_id)
        if not progress:
            return None
        return self._steps.get(progress.current_step)

    def get_step_data(self, step_id: str) -> Optional[Dict[str, Any]]:
        """Get step configuration data."""
        step = self._steps.get(step_id)
        return step.data if step else None

    def register_completion_callback(self, callback: Callable):
        """Register callback for onboarding completion."""
        self._completion_callbacks.append(callback)

    def _trigger_completion(self, progress: OnboardingProgress):
        """Trigger completion callbacks."""
        for callback in self._completion_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.error(f"Completion callback failed: {e}")

    def get_sample_configs(self) -> Dict[str, Any]:
        """Get sample configuration templates."""
        return {
            "zone_living_room": {
                "name": "Living Room",
                "entities": ["light.living_room", "switch.tv", "climate.living_room"],
                "presence_sensor": "binary_sensor.living_room_motion",
            },
            "automation_morning": {
                "name": "Morning Routine",
                "trigger": "sunrise",
                "actions": ["lights.on(50%)", "blinds.open()", "coffee.start()"],
            },
            "automation_evening": {
                "name": "Evening Routine",
                "trigger": "sunset",
                "actions": ["lights.on(30%)", "thermostat.set(21)", "tv.off()"],
            },
        }

    def get_tutorials(self) -> List[Dict[str, Any]]:
        """Get tutorial list."""
        return [
            {
                "id": "voice_basics",
                "title": "Voice Control Basics",
                "duration_min": 5,
                "topics": ["Wake Word", "Commands", "Responses"],
            },
            {
                "id": "automation_intro",
                "title": "Introduction to Automations",
                "duration_min": 10,
                "topics": ["Triggers", "Conditions", "Actions"],
            },
            {
                "id": "habit_learning",
                "title": "How Habit Learning Works",
                "duration_min": 8,
                "topics": ["Pattern Detection", "Suggestions", "Privacy"],
            },
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get onboarding statistics."""
        completed = len([p for p in self._progress.values() if p.completed_at])
        in_progress = len([p for p in self._progress.values() if not p.completed_at])
        
        return {
            "total_steps": len(self._steps),
            "users_started": len(self._progress),
            "users_completed": completed,
            "users_in_progress": in_progress,
            "completion_rate": completed / max(1, len(self._progress)) * 100,
        }


# Global default onboarding
default_onboarding: Optional[OnboardingWizard] = None


def init_onboarding_wizard() -> OnboardingWizard:
    """Initialize global onboarding wizard."""
    global default_onboarding
    default_onboarding = OnboardingWizard()
    return default_onboarding
