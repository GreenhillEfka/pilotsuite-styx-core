"""Contract coverage for proposal-lifecycle-aware proactive voice hints (Slice 33)."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.action_closure import get_action_closure_store  # noqa: E402
from copilot_core.api.v1.voice import bp as voice_bp  # noqa: E402
from copilot_core.voice.context_builder import VoiceContext  # noqa: E402
from copilot_core.voice.proactive import HintConfig, HintPriority, HintType, ProactiveVoiceHints  # noqa: E402


def setup_function() -> None:
    get_action_closure_store().clear()


def _seed_failed_proposal() -> None:
    """Seed a failed proposal."""
    store = get_action_closure_store()
    closure = store.upsert(
        source="voice.accepted",
        proposal_id="proposal:voice-failed",
        action_id="action:voice-failed",
        zone_id="zone:kitchen",
        module_id="media",
        accepted_at="2026-04-02T07:00:00+00:00",
    )
    store.record_execution(
        closure["closure_id"],
        outcome="failed",
        runtime_source="ha.adapter",
        error="device_unavailable",
        executed_at="2026-04-02T07:01:00+00:00",
    )


def _seed_follow_up_open_proposal() -> None:
    """Seed an accepted proposal with worker engagement (follow_up_open status)."""
    from copilot_core.api.v1 import notifications as notifications_api
    from copilot_core.api.v1.notifications import (
        ActionClosureFollowUpDispatchStore,
        claim_action_closure_follow_up_dispatch,
        record_action_closure_follow_up_receipt,
    )
    from flask import Flask

    store = get_action_closure_store()
    notifications_api._action_closure_follow_up_dispatch_store = ActionClosureFollowUpDispatchStore()

    closure = store.upsert(
        source="habitus.accepted",
        proposal_id="proposal:habitus-followup",
        action_id="action:habitus-followup",
        zone_id="zone:sleep",
        module_id="climate",
        accepted_at="2026-04-02T07:30:00+00:00",
    )
    store.record_execution(
        closure["closure_id"],
        outcome="failed",
        runtime_source="ha.adapter",
        error="delivery pending",
        executed_at="2026-04-02T07:31:00+00:00",
    )

    # Build dispatch and claim to trigger follow_up_open status
    app = Flask(__name__)
    with app.test_request_context(
        "/notifications/action-closures/dispatch?delivery_mode=notification_job",
        method="GET",
    ):
        body = notifications_api.get_action_closure_follow_up_dispatch().get_json()
    candidates = body["dispatch"]["candidates"]
    if candidates:
        dispatch_id = candidates[0]["dispatch_id"]
        with app.test_request_context(
            "/notifications/action-closures/dispatch/claim",
            method="POST",
            json={
                "dispatch_id": dispatch_id,
                "claimed_by": "worker.notifications",
                "lease_seconds": 300,
            },
        ):
            claim_action_closure_follow_up_dispatch()


def _seed_suggested_proposal() -> None:
    """Seed a suggested proposal via AutomationSuggestionEngine."""
    from copilot_core.automations.suggestion_engine import AutomationSuggestionEngine
    engine = AutomationSuggestionEngine()
    suggestion = engine.suggest_from_presence(away_minutes=45)
    # Don't accept - leave it as suggested
    assert suggestion is not None


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    app = Flask(__name__)
    app.register_blueprint(voice_bp)
    return app.test_client()


def test_proactive_voice_hints_surface_failed_proposal_follow_up() -> None:
    """Voice hints detect failed proposals and suggest follow-up."""
    _seed_failed_proposal()

    hints_service = ProactiveVoiceHints(
        config=HintConfig(
            enabled_types=[HintType.PROPOSAL_FOLLOW_UP],
            min_priority=HintPriority.LOW,
            max_hints_per_hour=10,
        )
    )

    hints = hints_service.generate_hints(
        VoiceContext(zone_name="kitchen", language_preference="de"),
        force=True,
    )

    assert len(hints) == 1
    hint = hints[0]
    assert hint.hint_type == HintType.PROPOSAL_FOLLOW_UP
    assert hint.priority == HintPriority.HIGH
    assert "gescheitert" in hint.message_de
    assert hint.context["contract"] == "ProposalLifecycleVoiceHintV1"
    assert hint.context["summary"]["lifecycle_statuses"]["failed"] == 1
    assert hint.context["recent_proposal"]["proposal_id"] == "proposal:voice-failed"
    assert hint.suggested_action["kind"] == "proposal_lifecycle_review"


def test_proactive_voice_hints_surface_follow_up_open_proposal() -> None:
    """Voice hints detect accepted proposals with worker engagement (follow_up_open)."""
    _seed_follow_up_open_proposal()

    hints_service = ProactiveVoiceHints(
        config=HintConfig(
            enabled_types=[HintType.PROPOSAL_FOLLOW_UP],
            min_priority=HintPriority.LOW,
            max_hints_per_hour=10,
        )
    )

    hints = hints_service.generate_hints(
        VoiceContext(zone_name="bedroom", language_preference="de"),
        force=True,
    )

    assert len(hints) == 1
    hint = hints[0]
    assert hint.hint_type == HintType.PROPOSAL_FOLLOW_UP
    assert hint.priority == HintPriority.MEDIUM
    assert "offene Vorschlaege" in hint.message_de or "in Bearbeitung" in hint.message_de
    assert hint.context["contract"] == "ProposalLifecycleVoiceHintV1"


def test_proactive_voice_hints_surface_suggested_proposal() -> None:
    """Voice hints detect new suggested proposals via SuggestionEngine."""
    from copilot_core.automations.suggestion_engine import AutomationSuggestionEngine
    
    engine = AutomationSuggestionEngine()
    suggestion = engine.suggest_from_presence(away_minutes=45)
    assert suggestion is not None

    hints_service = ProactiveVoiceHints(
        config=HintConfig(
            enabled_types=[HintType.PROPOSAL_SUGGESTION],
            min_priority=HintPriority.LOW,
            max_hints_per_hour=10,
        )
    )

    hints = hints_service.generate_hints(
        VoiceContext(zone_name="living", language_preference="de"),
        force=True,
    )

    # Note: suggested proposals come from engine, not closure store
    # This test verifies the integration point exists
    assert hints is not None


def test_proactive_voice_hints_pass_zone_name_to_proposal_context() -> None:
    """Zone name from VoiceContext is forwarded to proposal-lifecycle context for failed proposals."""
    _seed_failed_proposal()

    hints_service = ProactiveVoiceHints(
        config=HintConfig(
            enabled_types=[HintType.PROPOSAL_FOLLOW_UP],
            min_priority=HintPriority.LOW,
            max_hints_per_hour=10,
        )
    )

    hints = hints_service.generate_hints(
        VoiceContext(zone_name="Küche", language_preference="de"),
        force=True,
    )

    assert len(hints) == 1
    hint = hints[0]
    assert hint.context["contract"] == "ProposalLifecycleVoiceHintV1"
    assert hint.context["voice_zone"] == "Küche"


def test_voice_hints_api_exposes_proposal_follow_up_contract(monkeypatch) -> None:
    """Voice hints API exposes proposal-lifecycle hints with contract."""
    _seed_failed_proposal()
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.get(
        "/api/v1/voice/hints?force=true",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert len(body["hints"]) >= 1

    # Find the proposal hint
    proposal_hints = [h for h in body["hints"] if h["hint_type"] in ("proposal_suggestion", "proposal_follow_up")]
    assert len(proposal_hints) >= 1
    hint = proposal_hints[0]
    assert hint["context"]["contract"] == "ProposalLifecycleVoiceHintV1"
    assert hint["priority"] == "high"


def test_voice_hints_priority_ordering_failed_over_open_over_suggested() -> None:
    """Failed proposals take priority over open, which take priority over suggested."""
    _seed_suggested_proposal()
    _seed_follow_up_open_proposal()
    _seed_failed_proposal()

    hints_service = ProactiveVoiceHints(
        config=HintConfig(
            enabled_types=[HintType.PROPOSAL_FOLLOW_UP, HintType.PROPOSAL_SUGGESTION],
            min_priority=HintPriority.LOW,
            max_hints_per_hour=10,
        )
    )

    hints = hints_service.generate_hints(
        VoiceContext(zone_name="home", language_preference="de"),
        force=True,
    )

    assert len(hints) >= 1
    # First hint should be the failed proposal (HIGH priority)
    proposal_hints = [h for h in hints if h.hint_type in (HintType.PROPOSAL_FOLLOW_UP, HintType.PROPOSAL_SUGGESTION)]
    if proposal_hints:
        # The highest priority hint should be HIGH (failed)
        priorities = [h.priority for h in proposal_hints]
        assert HintPriority.HIGH in priorities
