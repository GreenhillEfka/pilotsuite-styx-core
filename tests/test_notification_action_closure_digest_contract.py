"""Contract coverage for closure-aware notification digest surfaces."""

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
    get_notification_digest,
    get_pending_notifications,
    get_action_closure_follow_up_dispatch,
    record_action_closure_follow_up_receipt,
)


def setup_function() -> None:
    get_action_closure_store().clear()
    notifications_api._notification_manager = NotificationManager()
    notifications_api._action_closure_follow_up_dispatch_store = ActionClosureFollowUpDispatchStore()


def _seed_closures() -> int:
    store = get_action_closure_store()
    store.upsert(
        source="voice.accepted",
        proposal_id="proposal:living:open",
        action_id="action:living:open",
        zone_id="zone:living",
        module_id="light",
        accepted_at="2026-04-01T21:00:00+00:00",
    )
    failing = store.upsert(
        source="predictive.accepted",
        proposal_id="proposal:sleep:failed",
        action_id="action:sleep:failed",
        zone_id="zone:sleep",
        module_id="climate",
        accepted_at="2026-04-01T21:01:00+00:00",
    )
    store.record_execution(
        failing["closure_id"],
        outcome="failed",
        runtime_source="ha.adapter",
        error="timeout",
        executed_at="2026-04-01T21:02:00+00:00",
    )
    return store.get_current_revision()


def test_notification_digest_can_embed_action_closure_digest_delta() -> None:
    base_revision = _seed_closures()
    store = get_action_closure_store()
    store.upsert(
        source="voice.accepted",
        proposal_id="proposal:living:new-open",
        action_id="action:living:new-open",
        zone_id="zone:living",
        module_id="scene",
        accepted_at="2026-04-01T21:03:00+00:00",
    )

    app = Flask(__name__)
    with app.test_request_context(
        f"/notifications/digest?include_action_closures=true&zone_id=zone:living&action_closure_since={base_revision}&recent_limit=5",
        method="GET",
    ):
        response = get_notification_digest()

    body = response.get_json()
    closure_digest = body["digest"]["action_closures"]
    assert closure_digest["contract"] == "ActionClosureNotificationDigestV1"
    assert closure_digest["zone_id"] == "zone:living"
    assert closure_digest["total_closures"] == 2
    assert closure_digest["open_count"] == 2
    assert closure_digest["failure_count"] == 0
    assert closure_digest["delta"]["since_revision"] == base_revision
    assert closure_digest["delta"]["changed"] is True
    assert closure_digest["delta"]["changed_count"] == 1
    assert len(closure_digest["follow_ups"]) == 2
    assert all(item["kind"] == "open" for item in closure_digest["follow_ups"])


def test_pending_notifications_surface_closure_follow_ups_even_without_new_delta() -> None:
    _seed_closures()
    current_revision = get_action_closure_store().get_current_revision()

    manager = notifications_api.get_notification_manager()
    manager.create_notification(
        title="Info",
        message="Digest check",
        priority="normal",
        type="info",
    )

    app = Flask(__name__)
    with app.test_request_context(
        f"/notifications/pending?include_action_closures=true&action_closure_since={current_revision}&recent_limit=5",
        method="GET",
    ):
        response = get_pending_notifications()

    body = response.get_json()
    closure_digest = body["action_closures"]
    assert body["count"] == 1
    assert closure_digest["contract"] == "ActionClosureNotificationDigestV1"
    assert closure_digest["delta"]["changed"] is False
    assert closure_digest["delta"]["changed_count"] == 0
    assert closure_digest["open_count"] == 1
    assert closure_digest["failure_count"] == 1
    kinds = {item["kind"] for item in closure_digest["follow_ups"]}
    assert kinds == {"open", "problematic"}


def test_notification_digest_embeds_delivery_receipt_summary_from_dispatch_results() -> None:
    _seed_closures()
    app = Flask(__name__)

    with app.test_request_context(
        "/notifications/action-closures/dispatch?delivery_mode=notification_job&recent_limit=5",
        method="GET",
    ):
        dispatch_response = get_action_closure_follow_up_dispatch()

    candidates = dispatch_response.get_json()["dispatch"]["candidates"]
    open_candidate = next(item for item in candidates if item["kind"] == "open")
    problematic_candidate = next(item for item in candidates if item["kind"] == "problematic")

    with app.test_request_context(
        "/notifications/action-closures/dispatch/ack",
        method="POST",
        json={"dispatch_id": open_candidate["dispatch_id"], "acknowledged_by": "worker.notifications"},
    ):
        acknowledge_action_closure_follow_up_dispatch()

    with app.test_request_context(
        "/notifications/action-closures/dispatch/receipt",
        method="POST",
        json={
            "dispatch_id": open_candidate["dispatch_id"],
            "receipt_state": "delivered",
            "receipt_by": "worker.notifications",
        },
    ):
        record_action_closure_follow_up_receipt()

    with app.test_request_context(
        "/notifications/action-closures/dispatch/receipt",
        method="POST",
        json={
            "dispatch_id": problematic_candidate["dispatch_id"],
            "receipt_state": "failed",
            "receipt_by": "worker.notifications",
            "retry_state": "scheduled",
            "retry_count": 1,
            "escalation_state": "pending",
            "escalation_reason": "retry needed",
        },
    ):
        record_action_closure_follow_up_receipt()

    with app.test_request_context(
        "/notifications/digest?include_action_closures=true&recent_limit=5",
        method="GET",
    ):
        response = get_notification_digest()

    body = response.get_json()
    receipt_summary = body["digest"]["action_closures"]["delivery_receipts"]
    assert receipt_summary["contract"] == "ActionClosureFollowUpReceiptSummaryV1"
    assert receipt_summary["counts"]["total_receipts"] == 2
    assert receipt_summary["counts"]["delivered"] == 1
    assert receipt_summary["counts"]["failed"] == 1
    assert receipt_summary["counts"]["retry_pending"] == 1
    assert receipt_summary["counts"]["escalated"] == 1
