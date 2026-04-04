"""Contract tests for Slice 74 voice multi-turn dialog surface."""

from __future__ import annotations

import pytest

from copilot_core.voice.control_engine import (
    Language,
    VoiceControlEngine,
    VoiceDialogStatus,
    VoiceIntentType,
    looks_like_follow_up_resume_request,
)


class TestVoiceDialogSurface:
    """Focused contract coverage for multi-turn voice dialog flows."""

    def test_dialog_carries_zone_context_across_turns(self) -> None:
        engine = VoiceControlEngine(Language.DE)

        first = engine.process_dialog_turn("Licht im Wohnzimmer an", session_id="voice-zone")
        second = engine.process_dialog_turn("heller", session_id="voice-zone")

        assert first["command"]["zone_id"] == "zone_living_room"
        assert second["command"]["intent_type"] == VoiceIntentType.BRIGHTEN.value
        assert second["command"]["zone_id"] == "zone_living_room"
        assert second["dialog"]["current_zone_id"] == "zone_living_room"

    def test_low_confidence_turn_enters_clarification_state(self) -> None:
        engine = VoiceControlEngine(Language.DE)

        result = engine.process_dialog_turn("Licht", session_id="voice-clarify")

        assert result["command"]["intent_type"] == VoiceIntentType.UNKNOWN.value
        assert result["response"]["requires_confirmation"] is True
        assert result["dialog"]["status"] == VoiceDialogStatus.AWAITING_CLARIFICATION.value
        assert "präzisiere" in result["response"]["text_de"].lower()

    def test_clarification_turn_merges_with_previous_ambiguous_turn(self) -> None:
        engine = VoiceControlEngine(Language.DE)

        engine.process_dialog_turn("Licht", session_id="voice-merge")
        clarified = engine.process_dialog_turn("im Schlafzimmer an", session_id="voice-merge")

        assert clarified["command"]["intent_type"] == VoiceIntentType.TURN_ON.value
        assert clarified["command"]["zone_id"] == "zone_bedroom"
        assert clarified["dialog"]["status"] == VoiceDialogStatus.ACTIVE.value
        assert clarified["dialog"]["pending_command"] is None

    def test_dialog_does_not_double_count_history_during_clarification_merge(self) -> None:
        engine = VoiceControlEngine(Language.DE)

        engine.process_dialog_turn("Licht", session_id="voice-history")
        engine.process_dialog_turn("im Schlafzimmer an", session_id="voice-history")

        history = engine.get_command_history(limit=10)

        assert len(history) == 2
        assert history[-1]["intent_type"] == VoiceIntentType.TURN_ON.value

    def test_dialog_attaches_proposal_follow_up_target(self) -> None:
        engine = VoiceControlEngine(Language.DE)

        result = engine.process_dialog_turn(
            "mach weiter",
            session_id="voice-proposal-follow-up",
            follow_up_target={
                "kind": "proposal",
                "proposal_id": "proposal:voice:123",
                "zone_id": "zone_living_room",
                "summary": "Heiz-Vorschlag prüfen.",
            },
        )

        assert result["response"]["requires_confirmation"] is False
        assert result["response"]["action_taken"]["intent"] == "dialog_follow_up"
        assert result["response"]["action_taken"]["target_kind"] == "proposal"
        assert result["response"]["action_taken"]["target_id"] == "proposal:voice:123"
        assert result["dialog"]["active_follow_up"]["target_kind"] == "proposal"
        assert result["dialog"]["status"] == VoiceDialogStatus.RESOLVED.value

    def test_dialog_attaches_action_closure_follow_up_target(self) -> None:
        engine = VoiceControlEngine(Language.DE)

        result = engine.process_dialog_turn(
            "wie steht es damit",
            session_id="voice-closure-follow-up",
            follow_up_target={
                "kind": "action_closure",
                "closure_id": "closure:voice:456",
                "zone_id": "zone_kitchen",
                "summary": "Letzten Fehlerlauf prüfen.",
            },
        )

        assert result["response"]["action_taken"]["intent"] == "dialog_follow_up"
        assert result["response"]["action_taken"]["target_kind"] == "action_closure"
        assert result["response"]["action_taken"]["target_id"] == "closure:voice:456"
        assert result["dialog"]["active_follow_up"]["target_kind"] == "action_closure"
        assert result["dialog"]["current_zone_id"] == "zone_kitchen"

    @pytest.mark.parametrize(
        ("language", "resume_phrase", "target_kind", "target_id"),
        [
            (Language.DE, "weiter damit", "proposal", "proposal:voice:extended-de"),
            (Language.DE, "mach damit weiter", "proposal", "proposal:voice:extended-de-variant"),
            (Language.DE, "wie stehts damit", "proposal", "proposal:voice:extended-de-contracted"),
            (Language.DE, "was ist damit", "proposal", "proposal:voice:extended-de-question"),
            (Language.DE, "noch offen", "proposal", "proposal:voice:extended-de-open"),
            (Language.EN, "continue", "action_closure", "closure:voice:extended-en-continue"),
            (Language.EN, "go on", "action_closure", "closure:voice:extended-en"),
            (Language.EN, "continue with", "action_closure", "closure:voice:extended-en-continue-with"),
            (Language.EN, "what about that", "action_closure", "closure:voice:extended-en-what-about-that"),
            (Language.EN, "still open", "action_closure", "closure:voice:extended-en-still-open"),
            (Language.EN, "check on it", "action_closure", "closure:voice:extended-en-check"),
            (Language.EN, "how's that going", "action_closure", "closure:voice:extended-en-natural"),
            (Language.EN, "how's it going", "action_closure", "closure:voice:extended-en-pronoun"),
            (Language.EN, "hows it going", "action_closure", "closure:voice:extended-en-pronoun-asr"),
        ],
    )
    def test_dialog_accepts_extended_follow_up_resume_phrases(
        self,
        language: Language,
        resume_phrase: str,
        target_kind: str,
        target_id: str,
    ) -> None:
        engine = VoiceControlEngine(language)

        assert looks_like_follow_up_resume_request(resume_phrase, language) is True

        result = engine.process_dialog_turn(
            resume_phrase,
            session_id=f"voice-extended-{language.value}-{target_kind}",
            follow_up_target={
                "kind": target_kind,
                "proposal_id": target_id if target_kind == "proposal" else None,
                "closure_id": target_id if target_kind == "action_closure" else None,
                "zone_id": "zone_living_room",
                "status": "open",
            },
        )

        assert result["response"]["action_taken"]["intent"] == "dialog_follow_up"
        assert result["response"]["action_taken"]["target_kind"] == target_kind
        assert result["response"]["action_taken"]["target_id"] == target_id
        assert result["dialog"]["status"] == VoiceDialogStatus.RESOLVED.value

    @pytest.mark.parametrize(
        ("session_id", "follow_up_target", "expected_target_kind", "expected_target_id"),
        [
            (
                "voice-follow-up-status-proposal",
                {
                    "kind": "proposal",
                    "proposal_id": "proposal:voice:status",
                    "zone_id": "zone_living_room",
                    "status": "In Progress",
                },
                "proposal",
                "proposal:voice:status",
            ),
            (
                "voice-follow-up-status-action-closure",
                {
                    "kind": "action_closure",
                    "closure_id": "closure:voice:status",
                    "zone_id": "zone_kitchen",
                    "status": "In Progress",
                },
                "action_closure",
                "closure:voice:status",
            ),
        ],
    )
    def test_dialog_normalizes_follow_up_status_on_successful_resume(
        self,
        session_id: str,
        follow_up_target: dict[str, str],
        expected_target_kind: str,
        expected_target_id: str,
    ) -> None:
        engine = VoiceControlEngine(Language.DE)

        engine.process_dialog_turn(
            "mach weiter",
            session_id=session_id,
            follow_up_target=follow_up_target,
        )

        resumed_follow_up_target = dict(follow_up_target)
        resumed_follow_up_target["status"] = "Needs Review"

        resumed = engine.process_dialog_turn(
            "wie steht es damit",
            session_id=session_id,
            follow_up_target=resumed_follow_up_target,
        )

        assert resumed["response"]["action_taken"]["intent"] == "dialog_follow_up"
        assert resumed["response"]["action_taken"]["target_kind"] == expected_target_kind
        assert resumed["response"]["action_taken"]["target_id"] == expected_target_id
        assert resumed["response"]["action_taken"]["status"] == "needs_review"
        assert resumed["dialog"]["active_follow_up"]["target_kind"] == expected_target_kind
        assert resumed["dialog"]["active_follow_up"]["target_id"] == expected_target_id
        assert resumed["dialog"]["active_follow_up"]["status"] == "needs_review"
        assert resumed["dialog"]["status"] == VoiceDialogStatus.RESOLVED.value
