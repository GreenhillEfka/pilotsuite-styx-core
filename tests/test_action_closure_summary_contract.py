"""Contract coverage for Slice 18 action-closure summary surfaces."""

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
from copilot_core.api.v1.action_closure import action_closure_bp  # noqa: E402
from copilot_core.api.v1 import notifications as notifications_api  # noqa: E402
from copilot_core.api.v1.notifications import (  # noqa: E402
    ActionClosureFollowUpDispatchStore,
    acknowledge_action_closure_follow_up_dispatch,
    claim_action_closure_follow_up_dispatch,
    get_action_closure_follow_up_dispatch,
    record_action_closure_follow_up_receipt,
    settle_action_closure_follow_up_dispatch,
)
from copilot_core.api.v1.zone_dashboard import _build_global_context, init_zone_dashboard_api  # noqa: E402
from copilot_core.core.action_closure_read_model import (  # noqa: E402
    build_action_closure_context_block,
    build_action_closure_summary_read_model,
)
from copilot_core.styx.chat_handler import ChatHandler  # noqa: E402


def setup_function() -> None:
    get_action_closure_store().clear()
    notifications_api._action_closure_follow_up_dispatch_store = ActionClosureFollowUpDispatchStore()
    init_zone_dashboard_api()


def _seed_closures() -> None:
    store = get_action_closure_store()

    alpha = store.upsert(
        source="voice.accepted",
        proposal_id="proposal:voice",
        action_id="action:voice",
        zone_id="zone:living",
        module_id="light",
        accepted_at="2026-04-01T20:00:00+00:00",
    )
    store.record_feedback(alpha["closure_id"], feedback="worked_well", comment="passt")
    store.record_execution(
        alpha["closure_id"],
        outcome="executed",
        runtime_source="ha.adapter",
        result={"status": "ok"},
        executed_at="2026-04-01T20:05:00+00:00",
    )

    beta = store.upsert(
        source="predictive.accepted",
        proposal_id="proposal:predictive",
        action_id="action:predictive",
        zone_id="zone:sleep",
        module_id="climate",
        accepted_at="2026-04-01T20:10:00+00:00",
    )
    store.record_execution(
        beta["closure_id"],
        outcome="failed",
        runtime_source="ha.adapter",
        error="timeout",
        executed_at="2026-04-01T20:12:00+00:00",
    )

    store.upsert(
        source="multizone.accepted",
        proposal_id="proposal:scene",
        action_id="action:scene",
        zone_id="zone:living",
        module_id="scene",
        subject_type="scene",
        subject_id="scene:arrival",
        accepted_at="2026-04-01T20:20:00+00:00",
    )


def _client() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["COPILOT_AUTH_TOKEN"] = "test-token"
    app.register_blueprint(action_closure_bp)
    return app


def test_action_closure_summary_read_model_aggregates_outcomes() -> None:
    _seed_closures()

    summary = build_action_closure_summary_read_model(get_action_closure_store()).to_dict()

    assert summary["contract"] == "ActionClosureSummaryV1"
    assert summary["revision"] >= 1
    assert summary["latest_change_at"]
    assert summary["total_closures"] == 3
    assert summary["open_count"] == 1
    assert summary["terminal_count"] == 2
    assert summary["success_count"] == 1
    assert summary["failure_count"] == 1
    assert summary["feedback_count"] == 1
    assert summary["states"]["accepted"] == 1
    assert summary["states"]["executed"] == 1
    assert summary["states"]["failed"] == 1
    assert summary["sources"]["voice.accepted"] == 1
    assert summary["zones"]["zone:living"] == 2
    assert summary["modules"]["light"] == 1
    assert summary["modules"]["scene"] == 1
    assert summary["recent_closures"][0]["closure_id"]
    assert summary["highlights"]
    assert summary["delta"]["contract"] == "ActionClosureDeltaV1"
    assert summary["delta"]["current_revision"] == summary["revision"]
    assert summary["delta"]["changed_count"] == 3


def test_action_closure_context_block_is_chat_ready() -> None:
    _seed_closures()

    context = build_action_closure_context_block(
        get_action_closure_store(),
        zone_id="zone:living",
        recent_limit=2,
    ).to_dict()

    assert context["contract"] == "ActionClosureContextBlockV1"
    assert context["revision"] >= 1
    assert context["summary"]["total_closures"] == 2
    assert context["summary"]["success_count"] == 1
    assert context["recent_closures"][0]["zone_id"] == "zone:living"
    assert any("Aktionsabschluesse" in line for line in context["context_lines"])


def test_action_closure_summary_delta_surface_tracks_changes_since_revision() -> None:
    _seed_closures()
    store = get_action_closure_store()
    base_revision = store.get_current_revision()

    delta_closure = store.upsert(
        source="voice.accepted",
        proposal_id="proposal:delta",
        action_id="action:delta",
        zone_id="zone:living",
        module_id="light",
        accepted_at="2026-04-01T20:25:00+00:00",
    )

    summary = build_action_closure_summary_read_model(
        store,
        zone_id="zone:living",
        since_revision=base_revision,
        recent_limit=2,
    ).to_dict()

    assert summary["total_closures"] == 3
    assert summary["delta"]["since_revision"] == base_revision
    assert summary["delta"]["current_revision"] == store.get_current_revision()
    assert summary["delta"]["changed"] is True
    assert summary["delta"]["changed_count"] == 1
    assert summary["delta"]["recent_closures"][0]["closure_id"] == delta_closure["closure_id"]


def test_action_closure_context_block_reports_no_delta_when_revision_is_current() -> None:
    _seed_closures()
    store = get_action_closure_store()
    current_revision = store.get_current_revision()

    context = build_action_closure_context_block(
        store,
        zone_id="zone:living",
        zone_name="Wohnzimmer",
        since_revision=current_revision,
    ).to_dict()

    assert context["delta"]["since_revision"] == current_revision
    assert context["delta"]["changed"] is False
    assert context["delta"]["changed_count"] == 0
    assert any("Keine Closure-Aenderungen seit Revision" in line for line in context["context_lines"])


def test_action_closure_summary_and_context_api_surface() -> None:
    _seed_closures()
    app = _client()
    client = app.test_client()
    headers = {"Authorization": "Bearer test-token", "X-Ingress-Path": "/api"}

    base_revision = get_action_closure_store().get_current_revision()
    get_action_closure_store().upsert(
        source="predictive.accepted",
        proposal_id="proposal:api-delta",
        action_id="action:api-delta",
        zone_id="zone:living",
        module_id="climate",
        accepted_at="2026-04-01T20:30:00+00:00",
    )

    summary_response = client.get("/api/v1/action-closures/summary", headers=headers)
    assert summary_response.status_code == 200
    summary_body = summary_response.get_json()
    assert summary_body["summary"]["contract"] == "ActionClosureSummaryV1"
    assert summary_body["summary"]["total_closures"] == 4

    context_response = client.get(
        f"/api/v1/action-closures/context?zone_id=zone:living&recent_limit=2&since={base_revision}",
        headers=headers,
    )
    assert context_response.status_code == 200
    context_body = context_response.get_json()
    assert context_body["context"]["contract"] == "ActionClosureContextBlockV1"
    assert context_body["context"]["summary"]["total_closures"] == 3
    assert len(context_body["context"]["recent_closures"]) == 2
    assert context_body["context"]["delta"]["changed"] is True
    assert context_body["context"]["delta"]["changed_count"] == 1


def test_zone_dashboard_global_context_exposes_action_closure_summary() -> None:
    _seed_closures()

    ctx = _build_global_context()

    assert ctx["action_closures"]["revision"] >= 1
    assert ctx["action_closures"]["freshness"]
    assert ctx["action_closures"]["total"] == 3
    assert ctx["action_closures"]["open"] == 1
    assert ctx["action_closures"]["successful"] == 1
    assert ctx["action_closures"]["problematic"] == 1
    assert ctx["action_closures"]["recent"]
    assert ctx["action_closures"]["zones_with_closures"] == 2
    zone_contexts = ctx["action_closures"]["zone_contexts"]
    assert len(zone_contexts) == 2
    living = next(item for item in zone_contexts if item["zone_id"] == "zone:living")
    assert living["context"]["contract"] == "ActionClosureContextBlockV1"
    assert living["context"]["summary"]["total_closures"] == 2
    assert any(
        "Wohnzimmer" in line or "Wohnbereich" in line
        for line in living["context"]["context_lines"]
    )


def test_zone_dashboard_global_context_delta_filters_unchanged_zone_contexts() -> None:
    _seed_closures()
    store = get_action_closure_store()
    base_revision = store.get_current_revision()

    ctx = _build_global_context(since_revision=base_revision)
    assert ctx["action_closures"]["delta"]["changed"] is False
    assert ctx["action_closures"]["zone_contexts"] == []

    store.upsert(
        source="predictive.accepted",
        proposal_id="proposal:delta-dashboard",
        action_id="action:delta-dashboard",
        zone_id="zone:sleep",
        module_id="climate",
        accepted_at="2026-04-01T20:40:00+00:00",
    )

    changed_ctx = _build_global_context(since_revision=base_revision)
    assert changed_ctx["action_closures"]["delta"]["changed"] is True
    assert changed_ctx["action_closures"]["delta"]["changed_count"] == 1
    assert len(changed_ctx["action_closures"]["zone_contexts"]) == 1
    assert changed_ctx["action_closures"]["zone_contexts"][0]["zone_id"] == "zone:sleep"


def test_chat_handler_home_context_mentions_action_closure_summary() -> None:
    _seed_closures()
    app = Flask(__name__)
    app.config["COPILOT_SERVICES"] = {}

    with app.app_context():
        handler = ChatHandler()
        home_context = handler._build_home_context()

    assert "Aktionsabschluesse" in home_context
    assert "erfolgreich" in home_context


def test_zone_dashboard_and_chat_surface_follow_up_receipts() -> None:
    _seed_closures()
    app = Flask(__name__)

    with app.test_request_context(
        "/notifications/action-closures/dispatch?delivery_mode=notification_job&recent_limit=5",
        method="GET",
    ):
        dispatch_response = get_action_closure_follow_up_dispatch()

    candidates = dispatch_response.get_json()["dispatch"]["candidates"]
    open_candidate = next(item for item in candidates if item["kind"] == "open")
    failing_candidate = next(item for item in candidates if item["kind"] == "problematic")

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
        "/notifications/action-closures/dispatch/claim",
        method="POST",
        json={
            "dispatch_id": failing_candidate["dispatch_id"],
            "claimed_by": "worker.notifications",
            "lease_seconds": 60,
        },
    ):
        claim_action_closure_follow_up_dispatch()

    claim_store = notifications_api.get_action_closure_follow_up_dispatch_store()
    claim_store._claim_index[failing_candidate["dedupe_key"]].lease_expires_at = "2026-04-01T20:13:00+00:00"

    with app.test_request_context(
        "/notifications/action-closures/dispatch/receipt",
        method="POST",
        json={
            "dispatch_id": failing_candidate["dispatch_id"],
            "receipt_state": "failed",
            "receipt_by": "worker.notifications",
            "retry_state": "scheduled",
            "retry_count": 1,
            "escalation_state": "pending",
            "escalation_reason": "needs follow-up",
        },
    ):
        record_action_closure_follow_up_receipt()

    ctx = _build_global_context()
    receipt_summary = ctx["action_closures"]["receipt_summary"]
    assert receipt_summary["contract"] == "ActionClosureFollowUpReceiptSummaryV1"
    assert receipt_summary["counts"]["total_receipts"] == 2
    assert receipt_summary["counts"]["retry_pending"] == 1
    assert receipt_summary["counts"]["escalated"] == 1
    assert receipt_summary["sla"]["counts"]["stale_retries"] == 1
    assert "escalation_due" in receipt_summary["sla"]["counts"]
    assert receipt_summary["claims"]["counts"]["expired_leases"] == 1
    assert receipt_summary["claims"]["counts"]["reassignable"] == 1

    with app.app_context():
        handler = ChatHandler()
        home_context = handler._build_home_context()

    assert "Follow-up-Zustellung" in home_context
    assert "Retry offen" in home_context
    assert "Retry veraltet" in home_context
    assert "Lease abgelaufen" in home_context


def test_zone_dashboard_and_chat_surface_follow_up_settlements() -> None:
    _seed_closures()
    app = Flask(__name__)

    with app.test_request_context(
        "/notifications/action-closures/dispatch?delivery_mode=notification_job&recent_limit=5",
        method="GET",
    ):
        dispatch_response = get_action_closure_follow_up_dispatch()

    candidates = dispatch_response.get_json()["dispatch"]["candidates"]
    open_candidate = next(item for item in candidates if item["kind"] == "open")
    failing_candidate = next(item for item in candidates if item["kind"] == "problematic")

    with app.test_request_context(
        "/notifications/action-closures/dispatch/claim",
        method="POST",
        json={"dispatch_id": open_candidate["dispatch_id"], "claimed_by": "worker.notifications", "lease_seconds": 120},
    ):
        claim_action_closure_follow_up_dispatch()

    with app.test_request_context(
        "/notifications/action-closures/dispatch/settle",
        method="POST",
        json={
            "dispatch_id": open_candidate["dispatch_id"],
            "settlement_state": "settled",
            "settled_by": "worker.notifications",
            "receipt_state": "delivered",
            "note": "mobile done",
        },
    ):
        settle_action_closure_follow_up_dispatch()

    with app.test_request_context(
        "/notifications/action-closures/dispatch/claim",
        method="POST",
        json={"dispatch_id": failing_candidate["dispatch_id"], "claimed_by": "worker.notifications", "lease_seconds": 120},
    ):
        claim_action_closure_follow_up_dispatch()

    with app.test_request_context(
        "/notifications/action-closures/dispatch/settle",
        method="POST",
        json={
            "dispatch_id": failing_candidate["dispatch_id"],
            "settlement_state": "abandoned",
            "settled_by": "worker.notifications",
            "receipt_state": "failed",
            "retry_state": "scheduled",
            "retry_count": 1,
            "escalation_state": "pending",
            "escalation_reason": "needs human follow-up",
        },
    ):
        settle_action_closure_follow_up_dispatch()

    ctx = _build_global_context()
    receipt_summary = ctx["action_closures"]["receipt_summary"]
    assert receipt_summary["settlements"]["contract"] == "ActionClosureFollowUpSettlementSummaryV1"
    assert receipt_summary["settlements"]["counts"]["settled"] == 1
    assert receipt_summary["settlements"]["counts"]["abandoned"] == 1
    assert receipt_summary["settlements"]["counts"]["reassignable"] == 1

    with app.app_context():
        handler = ChatHandler()
        home_context = handler._build_home_context()

    assert "abgeschlossen" in home_context
    assert "abgebrochen" in home_context


def test_action_closure_context_block_resolves_zone_name_for_chat_voice() -> None:
    """Zone-scoped closure block resolves friendly zone name into context lines."""
    _seed_closures()

    # wohnzimmer zone - no closures
    ctx_w = build_action_closure_context_block(
        get_action_closure_store(),
        zone_id="zone:wohnzimmer",
        recent_limit=3,
        zone_name="Wohnzimmer",
    ).to_dict()
    # The seed data has zone:living and zone:sleep, not zone:wohnzimmer
    assert ctx_w["summary"]["total_closures"] == 0

    # zone:living - two closures (voice + multizone)
    ctx_l = build_action_closure_context_block(
        get_action_closure_store(),
        zone_id="zone:living",
        recent_limit=3,
        zone_name="Wohnzimmer",
    ).to_dict()
    assert ctx_l["summary"]["total_closures"] == 2
    assert any("Wohnzimmer" in line for line in ctx_l["context_lines"])
    assert any("Zone:" in line for line in ctx_l["context_lines"])

    # zone:sleep - one closure (predictive, failed)
    ctx_s = build_action_closure_context_block(
        get_action_closure_store(),
        zone_id="zone:sleep",
        recent_limit=3,
        zone_name="Schlafzimmer",
    ).to_dict()
    assert ctx_s["summary"]["total_closures"] == 1
    assert ctx_s["summary"]["failure_count"] == 1
    assert any("Schlafzimmer" in line for line in ctx_s["context_lines"])


def test_action_closure_context_block_falls_back_to_zone_id_slug_when_zone_name_missing() -> None:
    """When zone_name is not provided, zone_id slug is resolved to friendly name."""
    _seed_closures()

    # Pass zone_id but no explicit zone_name -> should still show "Wohnzimmer"
    ctx = build_action_closure_context_block(
        get_action_closure_store(),
        zone_id="zone:living",
        recent_limit=3,
        # zone_name intentionally omitted
    ).to_dict()

    assert ctx["summary"]["total_closures"] == 2
    # Zone name should be resolved from zone_id slug "living"
    assert any("Wohnzimmer" in line or "Living" in line for line in ctx["context_lines"])
