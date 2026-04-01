"""Contract coverage for closure-aware proactive voice hints."""

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


def _seed_failed_closure() -> None:
    store = get_action_closure_store()
    closure = store.upsert(
        source="voice.accepted",
        proposal_id="proposal:voice-failed",
        action_id="action:voice-failed",
        zone_id="zone:living",
        module_id="light",
        accepted_at="2026-04-01T22:00:00+00:00",
    )
    store.record_execution(
        closure["closure_id"],
        outcome="failed",
        runtime_source="ha.adapter",
        error="timeout",
        executed_at="2026-04-01T22:01:00+00:00",
    )


def _seed_open_closure() -> None:
    get_action_closure_store().upsert(
        source="predictive.accepted",
        proposal_id="proposal:voice-open",
        action_id="action:voice-open",
        zone_id="zone:sleep",
        module_id="climate",
        accepted_at="2026-04-01T22:05:00+00:00",
    )


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    app = Flask(__name__)
    app.register_blueprint(voice_bp)
    return app.test_client()


def test_proactive_voice_hints_surface_problematic_action_closure_follow_up() -> None:
    _seed_failed_closure()

    hints_service = ProactiveVoiceHints(
        config=HintConfig(
            enabled_types=[HintType.ACTION_FOLLOW_UP],
            min_priority=HintPriority.LOW,
            max_hints_per_hour=10,
        )
    )

    hints = hints_service.generate_hints(
        VoiceContext(zone_name="wohnzimmer", language_preference="de"),
        force=True,
    )

    assert len(hints) == 1
    hint = hints[0]
    assert hint.hint_type == HintType.ACTION_FOLLOW_UP
    assert hint.priority == HintPriority.HIGH
    assert "problematisch" in hint.message_de
    assert hint.context["contract"] == "ActionClosureVoiceHintV1"
    assert hint.context["summary"]["failure_count"] == 1
    assert hint.context["recent_closure"]["closure_id"]
    assert hint.suggested_action["kind"] == "action_closure_review"


def test_proactive_voice_hints_pass_zone_name_to_closure_context() -> None:
    """Zone name from VoiceContext is forwarded to closure context for zone-scoped hints."""
    _seed_failed_closure()

    hints_service = ProactiveVoiceHints(
        config=HintConfig(
            enabled_types=[HintType.ACTION_FOLLOW_UP],
            min_priority=HintPriority.LOW,
            max_hints_per_hour=10,
        )
    )

    # Use a zone context that matches the failed closure's zone
    hints = hints_service.generate_hints(
        VoiceContext(zone_name="Wohnzimmer", language_preference="de"),
        force=True,
    )

    assert len(hints) == 1
    hint = hints[0]
    assert hint.context["contract"] == "ActionClosureVoiceHintV1"
    assert hint.context["voice_zone"] == "Wohnzimmer"
    assert hint.context["recent_closure"]["zone_id"] == "zone:living"


def test_voice_hints_api_exposes_open_action_follow_up_contract(monkeypatch) -> None:
    _seed_open_closure()
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.get(
        "/api/v1/voice/hints?type=action_follow_up&force=true",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["critical_count"] == 0
    assert body["queued_count"] == 1
    assert len(body["hints"]) == 1

    hint = body["hints"][0]
    assert hint["hint_type"] == "action_follow_up"
    assert hint["priority"] == "medium"
    assert hint["context"]["contract"] == "ActionClosureVoiceHintV1"
    assert hint["context"]["summary"]["open_count"] == 1
    assert hint["context"]["recent_closure"]["state"] == "accepted"
    assert hint["suggested_action"]["kind"] == "action_closure_summary"
