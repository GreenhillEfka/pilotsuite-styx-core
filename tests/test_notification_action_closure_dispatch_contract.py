"""Contract coverage for closure follow-up dispatch worker surfaces."""

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
from copilot_core.api.v1 import notifications as notifications_api  # noqa: E402
from copilot_core.api.v1.notifications import (  # noqa: E402
    ActionClosureFollowUpDispatchStore,
    NotificationManager,
    acknowledge_action_closure_follow_up_dispatch,
    get_action_closure_follow_up_dispatch,
)


def setup_function() -> None:
    get_action_closure_store().clear()
    notifications_api._notification_manager = NotificationManager()
    notifications_api._action_closure_follow_up_dispatch_store = ActionClosureFollowUpDispatchStore()


def _seed_closures() -> dict[str, object]:
    store = get_action_closure_store()
    open_closure = store.upsert(
        source="voice.accepted",
        proposal_id="proposal:living:open",
        action_id="action:living:open",
        zone_id="zone:living",
        module_id="light",
        accepted_at="2026-04-01T21:00:00+00:00",
    )
    failing_closure = store.upsert(
        source="predictive.accepted",
        proposal_id="proposal:sleep:failed",
        action_id="action:sleep:failed",
        zone_id="zone:sleep",
        module_id="climate",
        accepted_at="2026-04-01T21:01:00+00:00",
    )
    store.record_execution(
        failing_closure["closure_id"],
        outcome="failed",
        runtime_source="ha.adapter",
        error="timeout",
        executed_at="2026-04-01T21:02:00+00:00",
    )
    return {
        "open_closure_id": open_closure["closure_id"],
        "failing_closure_id": failing_closure["closure_id"],
        "revision": store.get_current_revision(),
    }


def test_dispatch_surface_materializes_same_closure_truth_for_notification_and_reminder_workers() -> None:
    seed = _seed_closures()
    app = Flask(__name__)

    with app.test_request_context(
        "/notifications/action-closures/dispatch?delivery_mode=notification_job&recent_limit=5",
        method="GET",
    ):
        notification_response = get_action_closure_follow_up_dispatch()

    with app.test_request_context(
        "/notifications/action-closures/dispatch?delivery_mode=reminder_queue&recent_limit=5",
        method="GET",
    ):
        reminder_response = get_action_closure_follow_up_dispatch()

    notification_body = notification_response.get_json()
    reminder_body = reminder_response.get_json()

    notification_dispatch = notification_body["dispatch"]
    reminder_dispatch = reminder_body["dispatch"]

    assert notification_dispatch["contract"] == "ActionClosureFollowUpDispatchV1"
    assert reminder_dispatch["contract"] == "ActionClosureFollowUpDispatchV1"
    assert notification_dispatch["counts"]["dispatchable"] == 2
    assert reminder_dispatch["counts"]["dispatchable"] == 2
    assert notification_dispatch["cursor"]["current_revision"] == seed["revision"]
    assert reminder_dispatch["cursor"]["current_revision"] == seed["revision"]

    notification_closures = {item["closure_id"] for item in notification_dispatch["candidates"]}
    reminder_closures = {item["closure_id"] for item in reminder_dispatch["candidates"]}
    assert notification_closures == reminder_closures
    assert notification_closures == {seed["open_closure_id"], seed["failing_closure_id"]}
    assert {item["delivery"]["mode"] for item in notification_dispatch["candidates"]} == {"notification_job"}
    assert {item["delivery"]["queue"] for item in notification_dispatch["candidates"]} == {"notifications"}
    assert {item["delivery"]["mode"] for item in reminder_dispatch["candidates"]} == {"reminder_queue"}
    assert {item["delivery"]["queue"] for item in reminder_dispatch["candidates"]} == {"reminders"}


def test_acknowledged_dispatch_candidate_stays_suppressed_until_closure_revision_changes() -> None:
    seed = _seed_closures()
    app = Flask(__name__)

    with app.test_request_context(
        "/notifications/action-closures/dispatch?delivery_mode=notification_job&recent_limit=5",
        method="GET",
    ):
        initial_response = get_action_closure_follow_up_dispatch()
    initial_candidates = initial_response.get_json()["dispatch"]["candidates"]
    open_candidate = next(item for item in initial_candidates if item["closure_id"] == seed["open_closure_id"])

    with app.test_request_context(
        "/notifications/action-closures/dispatch/ack",
        method="POST",
        json={
            "dispatch_id": open_candidate["dispatch_id"],
            "acknowledged_by": "worker.notifications",
            "note": "queued",
        },
    ):
        ack_response = acknowledge_action_closure_follow_up_dispatch()

    ack_body = ack_response.get_json()
    assert ack_body["ok"] is True
    assert ack_body["count"] == 1
    assert ack_body["acknowledged"][0]["dispatch_id"] == open_candidate["dispatch_id"]

    with app.test_request_context(
        f"/notifications/action-closures/dispatch?delivery_mode=notification_job&action_closure_since={seed['revision']}&recent_limit=5",
        method="GET",
    ):
        suppressed_response = get_action_closure_follow_up_dispatch()

    suppressed_dispatch = suppressed_response.get_json()["dispatch"]
    assert suppressed_dispatch["cursor"]["changed"] is False
    assert suppressed_dispatch["counts"]["acknowledged"] == 1
    assert all(item["closure_id"] != seed["open_closure_id"] for item in suppressed_dispatch["candidates"])
    assert {item["closure_id"] for item in suppressed_dispatch["candidates"]} == {seed["failing_closure_id"]}

    refreshed = get_action_closure_store().record_feedback(
        str(seed["open_closure_id"]),
        feedback="needs_follow_up",
        comment="Bitte erneut erinnern",
        actor="worker.notifications",
    )

    with app.test_request_context(
        f"/notifications/action-closures/dispatch?delivery_mode=notification_job&action_closure_since={seed['revision']}&recent_limit=5",
        method="GET",
    ):
        refreshed_response = get_action_closure_follow_up_dispatch()

    refreshed_dispatch = refreshed_response.get_json()["dispatch"]
    refreshed_candidate = next(item for item in refreshed_dispatch["candidates"] if item["closure_id"] == seed["open_closure_id"])
    assert refreshed_dispatch["cursor"]["changed"] is True
    assert refreshed_candidate["closure_revision"] == refreshed["revision"]
    assert refreshed_candidate["dispatch_id"] != open_candidate["dispatch_id"]


def test_dispatch_cursor_tracks_delta_without_hiding_unacknowledged_candidates() -> None:
    seed = _seed_closures()
    store = get_action_closure_store()
    store.upsert(
        source="habitus.accepted",
        proposal_id="proposal:kitchen:open",
        action_id="action:kitchen:open",
        zone_id="zone:kitchen",
        module_id="scene",
        accepted_at="2026-04-01T21:04:00+00:00",
    )
    current_revision = store.get_current_revision()
    app = Flask(__name__)

    with app.test_request_context(
        f"/notifications/action-closures/dispatch?delivery_mode=notification_job&action_closure_since={seed['revision']}&recent_limit=5",
        method="GET",
    ):
        changed_response = get_action_closure_follow_up_dispatch()

    changed_dispatch = changed_response.get_json()["dispatch"]
    assert changed_dispatch["cursor"]["since_revision"] == seed["revision"]
    assert changed_dispatch["cursor"]["current_revision"] == current_revision
    assert changed_dispatch["cursor"]["changed"] is True
    assert changed_dispatch["cursor"]["changed_count"] == 1
    assert changed_dispatch["counts"]["dispatchable"] == 3

    with app.test_request_context(
        f"/notifications/action-closures/dispatch?delivery_mode=notification_job&action_closure_since={current_revision}&recent_limit=5",
        method="GET",
    ):
        unchanged_response = get_action_closure_follow_up_dispatch()

    unchanged_dispatch = unchanged_response.get_json()["dispatch"]
    assert unchanged_dispatch["cursor"]["changed"] is False
    assert unchanged_dispatch["cursor"]["changed_count"] == 0
    assert unchanged_dispatch["counts"]["dispatchable"] == 3
