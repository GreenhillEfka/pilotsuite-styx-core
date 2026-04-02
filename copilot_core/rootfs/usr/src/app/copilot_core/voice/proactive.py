"""Proactive Voice Hints for context-aware suggestions.

Provides proactive voice hints based on:
- Mood changes
- Pattern recognition (Habitus)
- Time-based routines
- Important events
- Action-closure follow-ups
- Environmental changes

Features:
- Proaktive Hinweise bei wichtigen Erkenntnissen
- Integration mit Mood Engine und Habitus
- Outcome-aware Follow-ups aus der kanonischen Action-Closure-Surface
- Kontextbewusste Vorschläge
- DE/EN Sprachunterstützung
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .context_builder import VoiceContextBuilder, VoiceContext, TimeOfDay, MoodState
from ..mood.engine import MoodEngine, MoodState as EngineMoodState, MoodResult
from ..habitus.service import HabitusService
from ..action_closure import get_action_closure_store

_LOGGER = logging.getLogger(__name__)


class HintPriority(str, Enum):
    """Priority levels for proactive hints."""
    
    LOW = "low"  # Nice to know
    MEDIUM = "medium"  # Useful suggestion
    HIGH = "high"  # Important, should mention
    CRITICAL = "critical"  # Urgent, must mention immediately


class HintType(str, Enum):
    """Types of proactive hints."""
    
    # Mood-based hints
    MOOD_CHANGE = "mood_change"
    MOOD_SUGGESTION = "mood_suggestion"
    
    # Time-based hints
    TIME_ROUTINE = "time_routine"
    QUIET_HOURS = "quiet_hours"
    GOOD_MORNING = "good_morning"
    GOOD_NIGHT = "good_night"
    
    # Pattern-based hints
    HABITUS_PATTERN = "habitus_pattern"
    PREDICTIVE_ACTION = "predictive_action"
    
    # Proposal-based hints
    PROPOSAL_FOLLOW_UP = "proposal_follow_up"
    PROPOSAL_SUGGESTION = "proposal_suggestion"
    
    # Event-based hints
    IMPORTANT_EVENT = "important_event"
    REMINDER = "reminder"
    ACTION_FOLLOW_UP = "action_follow_up"
    
    # Environment-based hints
    WEATHER_ALERT = "weather_alert"
    ENERGY_SAVING = "energy_saving"
    COMFORT_SUGGESTION = "comfort_suggestion"
    
    # Device-based hints
    DEVICE_STATUS = "device_status"
    DEVICE_MAINTENANCE = "device_maintenance"


@dataclass
class ProactiveHint:
    """A proactive voice hint."""
    
    hint_type: HintType
    priority: HintPriority
    title_de: str
    title_en: str
    message_de: str
    message_en: str
    
    # Optional: suggested action
    suggested_action: Optional[Dict[str, Any]] = None
    
    # Metadata
    context: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hint_type": self.hint_type.value,
            "priority": self.priority.value,
            "title_de": self.title_de,
            "title_en": self.title_en,
            "message_de": self.message_de,
            "message_en": self.message_en,
            "suggested_action": self.suggested_action,
            "context": self.context,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
        }
    
    def get_message(self, language: str = "de") -> str:
        """Get hint message in specified language."""
        if language == "de":
            return self.message_de
        return self.message_en
    
    def get_title(self, language: str = "de") -> str:
        """Get hint title in specified language."""
        if language == "de":
            return self.title_de
        return self.title_en


@dataclass
class HintConfig:
    """Configuration for proactive hints."""
    
    # Enable/disable hint types
    enabled_types: List[HintType] = field(default_factory=lambda: list(HintType))
    
    # Priority threshold (only show hints at or above this priority)
    min_priority: HintPriority = HintPriority.LOW
    
    # Time-based settings
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "07:00"
    
    # Cooldown settings (avoid spam)
    hint_cooldown_seconds: int = 300  # 5 minutes between hints of same type
    max_hints_per_hour: int = 6
    
    # Context settings
    require_occupancy: bool = False  # Only hint when someone is home
    require_voice_activity: bool = False  # Only hint after voice interaction


class ProactiveVoiceHints:
    """Generates proactive voice hints based on context.
    
    Integration points:
    - Mood Engine: Detect mood changes and suggest actions
    - Habitus Service: Predictive hints based on patterns
    - Time context: Routine-based hints
    - Event store: Important events and reminders
    
    Usage:
    ```python
    hints = ProactiveVoiceHints(mood_engine, habitus_service)
    context = hints.context_builder.build_context(...)
    hints_list = hints.generate_hints(context)
    
    for hint in hints_list:
        if hint.priority == HintPriority.CRITICAL:
            # Interrupt and speak immediately
            tts.speak(hint.get_message())
        else:
            # Add to suggestion queue
            suggestions.append(hint)
    ```
    """
    
    # Mood change messages (DE)
    MOOD_CHANGE_DE = {
        EngineMoodState.RELAX: (
            "Entspannte Stimmung erkannt",
            "Die Stimmung ist entspannt. Möchtest du eine Chill-Playlist?",
        ),
        EngineMoodState.FOCUS: (
            "Fokussierte Stimmung erkannt",
            "Die Stimmung ist fokussiert. Soll ich Ablenkungen minimieren?",
        ),
        EngineMoodState.ACTIVE: (
            "Aktive Stimmung erkannt",
            "Die Stimmung ist aktiv. Passt auf, ich könnte das Licht heller machen.",
        ),
        EngineMoodState.NIGHT: (
            "Ruhige Stimmung erkannt",
            "Es ist ruhig geworden. Soll ich alles für die Nacht vorbereiten?",
        ),
        EngineMoodState.AWAY: (
            "Abwesenheit erkannt",
            "Niemand ist zuhause. Soll ich in den Abwesenheitsmodus wechseln?",
        ),
        EngineMoodState.NEUTRAL: (
            "Normale Stimmung",
            "Alles im normalen Bereich.",
        ),
    }
    
    # Mood change messages (EN)
    MOOD_CHANGE_EN = {
        EngineMoodState.RELAX: (
            "Relaxed mood detected",
            "The mood is relaxed. Would you like a chill playlist?",
        ),
        EngineMoodState.FOCUS: (
            "Focused mood detected",
            "The mood is focused. Should I minimize distractions?",
        ),
        EngineMoodState.ACTIVE: (
            "Active mood detected",
            "The mood is active. I could make the lights brighter.",
        ),
        EngineMoodState.NIGHT: (
            "Quiet mood detected",
            "It's gotten quiet. Should I prepare for night?",
        ),
        EngineMoodState.AWAY: (
            "Away detected",
            "No one is home. Should I switch to away mode?",
        ),
        EngineMoodState.NEUTRAL: (
            "Normal mood",
            "Everything is normal.",
        ),
    }
    
    # Time-based routine hints (DE)
    TIME_ROUTINES_DE = {
        TimeOfDay.MORNING: [
            (
                "Guten Morgen Routine",
                "Guten Morgen! Ich könnte die Jalousien öffnen und Kaffee vorbereiten.",
                {"domain": "scene", "service": "turn_on", "entity_id": "scene.morgen_routine"},
            ),
            (
                "Wetterbericht",
                "Soll ich dir den Wetterbericht für heute vorlesen?",
                None,
            ),
        ],
        TimeOfDay.AFTERNOON: [
            (
                "Nachmittagspause",
                "Zeit für eine Pause? Ich könnte eine kurze Entspannungssequenz starten.",
                None,
            ),
        ],
        TimeOfDay.EVENING: [
            (
                "Abendroutine",
                "Guten Abend! Soll ich die Abendroutine starten?",
                {"domain": "scene", "service": "turn_on", "entity_id": "scene.abend_routine"},
            ),
            (
                "Entspannung",
                "Möchtest du eine Entspannungs-Playlist oder einen Film starten?",
                None,
            ),
        ],
        TimeOfDay.NIGHT: [
            (
                "Gute Nacht",
                "Gute Nacht! Ich mache alles aus und aktiviere den Nachtwächter.",
                {"domain": "scene", "service": "turn_on", "entity_id": "scene.nacht_routine"},
            ),
        ],
    }
    
    # Time-based routine hints (EN)
    TIME_ROUTINES_EN = {
        TimeOfDay.MORNING: [
            (
                "Good morning routine",
                "Good morning! I could open the blinds and prepare coffee.",
                {"domain": "scene", "service": "turn_on", "entity_id": "scene.morning_routine"},
            ),
            (
                "Weather report",
                "Would you like me to read the weather forecast?",
                None,
            ),
        ],
        TimeOfDay.AFTERNOON: [
            (
                "Afternoon break",
                "Time for a break? I could start a short relaxation sequence.",
                None,
            ),
        ],
        TimeOfDay.EVENING: [
            (
                "Evening routine",
                "Good evening! Should I start the evening routine?",
                {"domain": "scene", "service": "turn_on", "entity_id": "scene.evening_routine"},
            ),
            (
                "Relaxation",
                "Would you like a relaxation playlist or to start a movie?",
                None,
            ),
        ],
        TimeOfDay.NIGHT: [
            (
                "Good night",
                "Good night! I'll turn everything off and activate night watch.",
                {"domain": "scene", "service": "turn_on", "entity_id": "scene.night_routine"},
            ),
        ],
    }
    
    def __init__(
        self,
        mood_engine: Optional[MoodEngine] = None,
        habitus_service: Optional[HabitusService] = None,
        config: Optional[HintConfig] = None,
    ):
        """Initialize proactive voice hints.
        
        Args:
            mood_engine: Mood engine for mood-based hints
            habitus_service: Habitus service for pattern-based hints
            config: Hint configuration
        """
        self.mood_engine = mood_engine
        self.habitus_service = habitus_service
        self.config = config or HintConfig()
        self.context_builder = VoiceContextBuilder()
        
        # Track last hints to avoid spam
        self._last_hints: Dict[HintType, datetime] = {}
        self._hints_this_hour: int = 0
        self._hour_reset: datetime = datetime.now(timezone.utc)
        
        # Track mood state for change detection
        self._last_mood: Optional[EngineMoodState] = None
        self._last_mood_time: Optional[datetime] = None
    
    def generate_hints(
        self,
        context: Optional[VoiceContext] = None,
        force: bool = False,
    ) -> List[ProactiveHint]:
        """Generate proactive hints based on current context.
        
        Args:
            context: Current voice context (built if None)
            force: Force generation (ignore cooldowns)
            
        Returns:
            List of ProactiveHint, sorted by priority
        """
        # Build context if not provided
        if context is None:
            context = self.context_builder.build_context(
                mood_engine=self.mood_engine,
                habitus_service=self.habitus_service,
            )
        
        # Check if we should generate hints
        if not force and not self._should_generate_hints(context):
            return []
        
        hints = []
        
        # Generate different types of hints
        hints.extend(self._check_mood_changes(context))
        hints.extend(self._check_time_routines(context))
        hints.extend(self._check_habitus_patterns(context))
        hints.extend(self._check_proposal_lifecycle(context))
        hints.extend(self._check_action_followups(context))
        hints.extend(self._check_environment_hints(context))
        
        # Filter by priority and cooldown
        filtered_hints = self._filter_hints(hints, force)
        
        # Sort by priority
        priority_order = {
            HintPriority.CRITICAL: 0,
            HintPriority.HIGH: 1,
            HintPriority.MEDIUM: 2,
            HintPriority.LOW: 3,
        }
        filtered_hints.sort(key=lambda h: priority_order.get(h.priority, 99))
        
        # Update tracking
        for hint in filtered_hints[:1]:  # Track only the top hint
            self._last_hints[hint.hint_type] = datetime.now(timezone.utc)
        
        return filtered_hints
    
    def _should_generate_hints(self, context: VoiceContext) -> bool:
        """Check if we should generate hints (respect cooldowns)."""
        now = datetime.now(timezone.utc)
        
        # Reset hourly counter
        if now - self._hour_reset > timedelta(hours=1):
            self._hints_this_hour = 0
            self._hour_reset = now
        
        # Check max hints per hour
        if self._hints_this_hour >= self.config.max_hints_per_hour:
            return False
        
        # Check occupancy requirement
        if self.config.require_occupancy:
            if context.current_zone and not context.current_zone.is_occupied:
                return False
        
        return True
    
    def _check_mood_changes(self, context: VoiceContext) -> List[ProactiveHint]:
        """Check for mood changes and generate hints."""
        hints = []
        
        if self.mood_engine is None or context.mood_state is None:
            return hints
        
        current_mood = context.mood_state
        now = datetime.now(timezone.utc)
        
        # Check for mood change
        if self._last_mood is not None and current_mood != self._last_mood:
            # Mood changed - generate hint
            mood_messages_de = self.MOOD_CHANGE_DE.get(
                current_mood, self.MOOD_CHANGE_DE[EngineMoodState.NEUTRAL]
            )
            mood_messages_en = self.MOOD_CHANGE_EN.get(
                current_mood, self.MOOD_CHANGE_EN[EngineMoodState.NEUTRAL]
            )
            
            hint = ProactiveHint(
                hint_type=HintType.MOOD_CHANGE,
                priority=HintPriority.MEDIUM,
                title_de=mood_messages_de[0],
                title_en=mood_messages_en[0],
                message_de=mood_messages_de[1],
                message_en=mood_messages_en[1],
                context={
                    "previous_mood": self._last_mood.value if self._last_mood else None,
                    "current_mood": current_mood.value,
                    "confidence": context.mood_confidence,
                },
            )
            hints.append(hint)
        
        # Update last mood
        self._last_mood = current_mood
        self._last_mood_time = now
        
        # Generate mood-based suggestions
        if context.mood_state == EngineMoodState.RELAX:
            hints.append(ProactiveHint(
                hint_type=HintType.MOOD_SUGGESTION,
                priority=HintPriority.LOW,
                title_de="Entspannungs-Vorschlag",
                title_en="Relaxation Suggestion",
                message_de="Die Stimmung ist entspannt. Möchtest du eine Chill-Playlist?",
                message_en="The mood is relaxed. Would you like a chill playlist?",
                suggested_action={
                    "domain": "media_player",
                    "service": "play_media",
                    "media_content_type": "playlist",
                },
            ))
        
        elif context.mood_state == EngineMoodState.FOCUS:
            hints.append(ProactiveHint(
                hint_type=HintType.MOOD_SUGGESTION,
                priority=HintPriority.LOW,
                title_de="Fokus-Vorschlag",
                title_en="Focus Suggestion",
                message_de="Die Stimmung ist fokussiert. Soll ich Ablenkungen minimieren?",
                message_en="The mood is focused. Should I minimize distractions?",
                suggested_action={
                    "domain": "automation",
                    "service": "turn_on",
                    "entity_id": "automation.fokus_modus",
                },
            ))
        
        elif context.mood_state == EngineMoodState.NIGHT:
            hints.append(ProactiveHint(
                hint_type=HintType.MOOD_SUGGESTION,
                priority=HintPriority.MEDIUM,
                title_de="Nacht-Vorschlag",
                title_en="Night Suggestion",
                message_de="Es ist ruhig geworden. Soll ich alles für die Nacht vorbereiten?",
                message_en="It's gotten quiet. Should I prepare for night?",
                suggested_action={
                    "domain": "scene",
                    "service": "turn_on",
                    "entity_id": "scene.nacht_routine",
                },
            ))
        
        return hints
    
    def _check_time_routines(self, context: VoiceContext) -> List[ProactiveHint]:
        """Check for time-based routine hints."""
        hints = []
        
        if context.time_context is None:
            return hints
        
        time_of_day = context.time_context.time_of_day
        
        # Get time-based routines
        routines_de = self.TIME_ROUTINES_DE.get(time_of_day, [])
        routines_en = self.TIME_ROUTINES_EN.get(time_of_day, [])
        
        # Only suggest once per time period
        time_key = f"time_routine:{time_of_day.value}"
        if time_key in self._last_hints:
            last_hint_time = self._last_hints[time_key]
            if datetime.now(timezone.utc) - last_hint_time < timedelta(hours=2):
                return hints
        
        # Add routine hints
        for i, (routine_de, routine_en) in enumerate(zip(routines_de, routines_en)):
            if i < len(routines_de):
                action = routine_de[2] if len(routine_de) > 2 else None
                hints.append(ProactiveHint(
                    hint_type=HintType.TIME_ROUTINE,
                    priority=HintPriority.MEDIUM if i == 0 else HintPriority.LOW,
                    title_de=routine_de[0],
                    title_en=routine_en[0],
                    message_de=routine_de[1],
                    message_en=routine_en[1],
                    suggested_action=action,
                    context={"time_of_day": time_of_day.value},
                ))
        
        # Check for quiet hours
        if context.time_context.is_quiet_hours:
            hints.append(ProactiveHint(
                hint_type=HintType.QUIET_HOURS,
                priority=HintPriority.HIGH,
                title_de="Ruhezeit",
                title_en="Quiet Hours",
                message_de="Es ist Ruhezeit. Ich werde Benachrichtigungen dämpfen.",
                message_en="It's quiet hours. I'll dampen notifications.",
                context={"quiet_hours": True},
            ))
        
        return hints
    
    def _check_habitus_patterns(self, context: VoiceContext) -> List[ProactiveHint]:
        """Check for habitus pattern-based hints."""
        hints = []
        
        if self.habitus_service is None:
            return hints
        
        try:
            # Get recent patterns
            patterns = self.habitus_service.list_recent_patterns(limit=3)
            
            for pattern in patterns:
                metadata = pattern.get("metadata", {})
                antecedent = metadata.get("antecedent", {})
                consequent = metadata.get("consequent", {})
                
                if antecedent and consequent:
                    # Create predictive hint
                    hints.append(ProactiveHint(
                        hint_type=HintType.PREDICTIVE_ACTION,
                        priority=HintPriority.MEDIUM,
                        title_de="Muster erkannt",
                        title_en="Pattern Detected",
                        message_de=f"Basierend auf Mustern: Nach {antecedent.get('full', '')} folgt oft {consequent.get('full', '')}.",
                        message_en=f"Based on patterns: {consequent.get('full', '')} often follows {antecedent.get('full', '')}.",
                        suggested_action={
                            "domain": antecedent.get("service", "automation"),
                            "service": "turn_on",
                            "entity_id": antecedent.get("entity", ""),
                        },
                        context={
                            "pattern_id": pattern.get("pattern_id"),
                            "confidence": pattern.get("evidence", {}).get("confidence", 0),
                        },
                    ))
        
        except Exception as e:
            _LOGGER.debug("Failed to check habitus patterns: %s", e)
        
        return hints

    def _check_proposal_lifecycle(self, context: VoiceContext) -> List[ProactiveHint]:
        """Check canonical proposal-lifecycle truth and suggest follow-ups for open/suggested proposals."""
        try:
            from copilot_core.core.proposal_lifecycle_read_model import build_proposal_lifecycle_context_block

            proposal_context = build_proposal_lifecycle_context_block(
                get_action_closure_store(),
                recent_limit=3,
                zone_name=context.zone_name,
            )
        except Exception as exc:
            _LOGGER.debug("Failed to build proposal-lifecycle follow-up hint: %s", exc)
            return []

        summary = dict(proposal_context.summary)
        total_proposals = int(summary.get("total_proposals") or 0)
        if total_proposals <= 0:
            return []

        lifecycle_statuses = summary.get("lifecycle_statuses") or {}
        suggested_count = int(lifecycle_statuses.get("suggested") or 0)
        accepted_count = int(lifecycle_statuses.get("accepted") or 0)
        follow_up_open_count = int(lifecycle_statuses.get("follow_up_open") or 0)
        failed_count = int(lifecycle_statuses.get("failed") or 0)

        recent_statuses = [dict(item) for item in proposal_context.recent_statuses]

        base_context = {
            "contract": "ProposalLifecycleVoiceHintV1",
            "summary": summary,
            "voice_zone": context.zone_name,
        }

        # Priority 1: Failed proposals need immediate follow-up
        failed_proposal = next(
            (item for item in recent_statuses if item.get("lifecycle_status") == "failed"),
            None,
        )
        if failed_proposal or failed_count:
            target = self._describe_proposal_target(failed_proposal)
            return [
                ProactiveHint(
                    hint_type=HintType.PROPOSAL_FOLLOW_UP,
                    priority=HintPriority.HIGH,
                    title_de="Vorschlag gescheitert",
                    title_en="Proposal Failed",
                    message_de=(
                        f"Der letzte Vorschlag bei {target} ist gescheitert. "
                        "Soll ich den Status pruefen oder einen neuen Versuch vorbereiten?"
                    ),
                    message_en=(
                        f"The latest proposal for {target} failed. "
                        "Should I check the status or prepare a retry?"
                    ),
                    suggested_action={
                        "kind": "proposal_lifecycle_review",
                        "proposal_id": failed_proposal.get("proposal_id") if failed_proposal else None,
                        "lifecycle_status": "failed",
                    },
                    context={
                        **base_context,
                        "recent_proposal": failed_proposal,
                    },
                )
            ]

        # Priority 2: Follow-up open (accepted but awaiting execution/settlement)
        follow_up_proposal = next(
            (item for item in recent_statuses if item.get("lifecycle_status") == "follow_up_open"),
            None,
        )
        if follow_up_proposal or follow_up_open_count:
            target = self._describe_proposal_target(follow_up_proposal)
            return [
                ProactiveHint(
                    hint_type=HintType.PROPOSAL_FOLLOW_UP,
                    priority=HintPriority.MEDIUM,
                    title_de="Vorschlag in Bearbeitung",
                    title_en="Proposal In Progress",
                    message_de=(
                        f"Es gibt offene Vorschlaege rund um {target}. "
                        "Soll ich den aktuellen Status zusammenfassen?"
                    ),
                    message_en=(
                        f"There are open proposals around {target}. "
                        "Should I summarize the current status?"
                    ),
                    suggested_action={
                        "kind": "proposal_lifecycle_summary",
                        "open_count": follow_up_open_count,
                        "proposal_id": follow_up_proposal.get("proposal_id") if follow_up_proposal else None,
                    },
                    context={
                        **base_context,
                        "recent_proposal": dict(follow_up_proposal) if follow_up_proposal else None,
                    },
                )
            ]

        # Priority 3: New suggestions awaiting acceptance
        suggested_proposal = next(
            (item for item in recent_statuses if item.get("lifecycle_status") == "suggested"),
            None,
        )
        if suggested_proposal or suggested_count:
            target = self._describe_proposal_target(suggested_proposal)
            return [
                ProactiveHint(
                    hint_type=HintType.PROPOSAL_SUGGESTION,
                    priority=HintPriority.MEDIUM,
                    title_de="Neuer Vorschlag verfuegbar",
                    title_en="New Proposal Available",
                    message_de=(
                        f"Es gibt einen neuen Vorschlag fuer {target}. "
                        "Soll ich ihn vorstellen?"
                    ),
                    message_en=(
                        f"There is a new proposal for {target}. "
                        "Should I present it?"
                    ),
                    suggested_action={
                        "kind": "proposal_present",
                        "proposal_id": suggested_proposal.get("proposal_id") if suggested_proposal else None,
                    },
                    context={
                        **base_context,
                        "recent_proposal": dict(suggested_proposal) if suggested_proposal else None,
                    },
                )
            ]

        return []

    @staticmethod
    def _describe_proposal_target(proposal: Optional[Dict[str, Any]]) -> str:
        """Build a short human-readable target label for a proposal hint."""
        if not proposal:
            return "dem letzten Vorschlag"

        zone_id = str(proposal.get("zone_id") or "").strip()
        module_id = str(proposal.get("module_id") or "").strip()
        proposal_id = str(proposal.get("proposal_id") or "").strip()

        if zone_id and module_id:
            return f"{zone_id}/{module_id}"
        if zone_id:
            return zone_id
        if module_id:
            return module_id
        if proposal_id:
            return proposal_id
        return "dem letzten Vorschlag"

    def _check_action_followups(self, context: VoiceContext) -> List[ProactiveHint]:
        """Check shared action-closure truth and suggest follow-ups for open/problematic actions."""
        try:
            from copilot_core.action_closure import get_action_closure_store
            from copilot_core.core.action_closure_read_model import build_action_closure_context_block

            closure_context = build_action_closure_context_block(
                get_action_closure_store(),
                recent_limit=3,
                zone_name=context.zone_name,
            )
        except Exception as exc:
            _LOGGER.debug("Failed to build action-closure follow-up hint: %s", exc)
            return []

        summary = dict(closure_context.summary)
        if int(summary.get("total_closures") or 0) <= 0:
            return []

        recent_closures = [dict(item) for item in closure_context.recent_closures]
        problematic = next(
            (
                item
                for item in recent_closures
                if str(item.get("state") or "").strip().lower() in {"failed", "error", "blocked", "denied", "rejected", "cancelled"}
                or str(item.get("execution_outcome") or "").strip().lower() in {"failed", "error", "blocked", "denied", "rejected", "cancelled"}
            ),
            None,
        )
        open_item = next(
            (
                item
                for item in recent_closures
                if str(item.get("state") or "").strip().lower() in {"accepted", "feedback_received", "queued", "pending", "scheduled", "awaiting_execution"}
            ),
            None,
        )

        base_context = {
            "contract": "ActionClosureVoiceHintV1",
            "summary": summary,
            "voice_zone": context.zone_name,
        }

        if problematic:
            target = self._describe_closure_target(problematic)
            return [
                ProactiveHint(
                    hint_type=HintType.ACTION_FOLLOW_UP,
                    priority=HintPriority.HIGH,
                    title_de="Aktion braucht Nachfassen",
                    title_en="Action Needs Follow-Up",
                    message_de=(
                        f"Die letzte Aktion bei {target} war problematisch. "
                        "Soll ich den Status pruefen oder einen neuen Versuch vorbereiten?"
                    ),
                    message_en=(
                        f"The latest action for {target} was problematic. "
                        "Should I check the status or prepare a retry?"
                    ),
                    suggested_action={
                        "kind": "action_closure_review",
                        "closure_id": problematic.get("closure_id"),
                        "state": problematic.get("state"),
                    },
                    context={
                        **base_context,
                        "recent_closure": problematic,
                    },
                )
            ]

        open_count = int(summary.get("open_count") or 0)
        if open_item or open_count:
            target = self._describe_closure_target(open_item) if open_item else f"{open_count} offenen Aktionen"
            return [
                ProactiveHint(
                    hint_type=HintType.ACTION_FOLLOW_UP,
                    priority=HintPriority.MEDIUM,
                    title_de="Offene Aktion im Blick behalten",
                    title_en="Keep an Eye on Open Action",
                    message_de=(
                        f"Es gibt noch offene Aktionen rund um {target}. "
                        "Soll ich den aktuellen Status zusammenfassen?"
                    ),
                    message_en=(
                        f"There are still open actions around {target}. "
                        "Should I summarize the current status?"
                    ),
                    suggested_action={
                        "kind": "action_closure_summary",
                        "open_count": open_count,
                        "closure_id": (open_item or {}).get("closure_id"),
                    },
                    context={
                        **base_context,
                        "recent_closure": dict(open_item) if open_item else None,
                    },
                )
            ]

        return []

    @staticmethod
    def _describe_closure_target(closure: Optional[Dict[str, Any]]) -> str:
        """Build a short human-readable target label for a closure hint."""
        if not closure:
            return "dem letzten Vorgang"

        zone_id = str(closure.get("zone_id") or "").strip()
        module_id = str(closure.get("module_id") or "").strip()
        action_id = str(closure.get("action_id") or "").strip()

        if zone_id and module_id:
            return f"{zone_id}/{module_id}"
        if zone_id:
            return zone_id
        if module_id:
            return module_id
        if action_id:
            return action_id
        return "dem letzten Vorgang"

    def _check_environment_hints(self, context: VoiceContext) -> List[ProactiveHint]:
        """Check for environment-based hints (weather, energy, comfort)."""
        hints = []
        
        # Check for comfort suggestions based on mood
        if context.mood_state == EngineMoodState.RELAX:
            hints.append(ProactiveHint(
                hint_type=HintType.COMFORT_SUGGESTION,
                priority=HintPriority.LOW,
                title_de="Komfort-Vorschlag",
                title_en="Comfort Suggestion",
                message_de="Die Stimmung ist entspannt. Soll ich die Beleuchtung anpassen?",
                message_en="The mood is relaxed. Should I adjust the lighting?",
                suggested_action={
                    "domain": "light",
                    "service": "turn_on",
                    "service_data": {"brightness_pct": 40, "kelvin": 2700},
                },
            ))
        
        # Check for energy saving opportunities
        if context.current_zone and not context.current_zone.is_occupied:
            hints.append(ProactiveHint(
                hint_type=HintType.ENERGY_SAVING,
                priority=HintPriority.MEDIUM,
                title_de="Energiespar-Vorschlag",
                title_en="Energy Saving",
                message_de=f"{context.current_zone.zone_name} ist leer. Soll ich das Licht ausschalten?",
                message_en=f"{context.current_zone.zone_name} is empty. Should I turn off the lights?",
                suggested_action={
                    "domain": "light",
                    "service": "turn_off",
                    "entity_id": f"light.{context.current_zone.zone_name}",
                },
            ))
        
        return hints
    
    def _filter_hints(
        self,
        hints: List[ProactiveHint],
        force: bool = False,
    ) -> List[ProactiveHint]:
        """Filter hints by priority and cooldown."""
        now = datetime.now(timezone.utc)
        filtered = []
        
        for hint in hints:
            # Check if hint type is enabled
            if hint.hint_type not in self.config.enabled_types:
                continue
            
            # Check priority threshold
            priority_order = {
                HintPriority.LOW: 0,
                HintPriority.MEDIUM: 1,
                HintPriority.HIGH: 2,
                HintPriority.CRITICAL: 3,
            }
            if priority_order[hint.priority] < priority_order[self.config.min_priority]:
                continue
            
            # Check cooldown (unless force)
            if not force:
                last_hint_time = self._last_hints.get(hint.hint_type)
                if last_hint_time:
                    cooldown = timedelta(seconds=self.config.hint_cooldown_seconds)
                    if now - last_hint_time < cooldown:
                        continue
            
            # Check expiration
            if hint.expires_at and now > hint.expires_at:
                continue
            
            filtered.append(hint)
        
        return filtered
    
    def get_critical_hints(self, context: Optional[VoiceContext] = None) -> List[ProactiveHint]:
        """Get only critical hints for immediate delivery."""
        hints = self.generate_hints(context)
        return [h for h in hints if h.priority == HintPriority.CRITICAL]
    
    def get_queued_hints(self, context: Optional[VoiceContext] = None) -> List[ProactiveHint]:
        """Get non-critical hints for queued delivery."""
        hints = self.generate_hints(context)
        return [h for h in hints if h.priority != HintPriority.CRITICAL]
    
    def clear_tracking(self):
        """Clear hint tracking data."""
        self._last_hints.clear()
        self._hints_this_hour = 0
        self._hour_reset = datetime.now(timezone.utc)
        self._last_mood = None
        self._last_mood_time = None
