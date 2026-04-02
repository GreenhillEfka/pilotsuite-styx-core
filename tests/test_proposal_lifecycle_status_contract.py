"""Contract coverage for Slice 30 proposal lifecycle status surfaces."""

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
    claim_action_closure_follow_up_dispatch,
    get_action_closure_follow_up_dispatch,
    record_action_closure_follow_up_receipt,
    settle_action_closure_follow_up_dispatch,
)
from copilot_core.api.v1.proposals import init_proposals_api, proposals_bp  # noqa: E402
from copilot_core.automations.suggestion_engine import AutomationSuggestionEngine  # noqa: E402
from copilot_core.core.proposal_lifecycle_read_model import (  # noqa: E402
    build_proposal_lifecycle_status_summary,
    get_proposal_lifecycle_status,
)
from copilot_core.api.v1.zone_dashboard import _build_global_context, init_zone_dashboard_api  # noqa: E402
from copilot_core.styx.chat_handler import ChatHandler  # noqa: E402


def setup_function() -> None:
    get_action_closure_store().clear()
    notifications_api._action_closure_follow_up_dispatch_store = ActionClosureFollowUpDispatchStore()
    init_zone_dashboard_api()


def _build_dispatch_index() -> dict[str, dict[str, object]]:
    app = Flask(__name__)
    with app.test_request_context(
        "/notifications/action-closures/dispatch?delivery_mode=notification_job&recent_limit=10",
        method="GET",
    ):
        body = get_action_closure_follow_up_dispatch().get_json()
    return {
        item["closure_id"]: item
        for item in body["dispatch"]["candidates"]
    }


def _seed_statuses() -> dict[str, str]:
    store = get_action_closure_store()

    accepted = store.upsert(
        source="voice.accepted",
        proposal_id="proposal:accepted",
        action_id="action:accepted",
        zone_id="zone:living",
        module_id="light",
        accepted_at="2026-04-02T00:10:00+00:00",
    )

    executed = store.upsert(
        source="predictive.accepted",
        proposal_id="proposal:executed",
        action_id="action:executed",
        zone_id="zone:sleep",
        module_id="climate",
        accepted_at="2026-04-02T00:11:00+00:00",
    )
    store.record_execution(
        executed["closure_id"],
        outcome="executed",
        runtime_source="ha.adapter",
        result={"ok": True},
        executed_at="2026-04-02T00:12:00+00:00",
    )

    failed = store.upsert(
        source="predictive.accepted",
        proposal_id="proposal:failed",
        action_id="action:failed",
        zone_id="zone:office",
        module_id="scene",
        accepted_at="2026-04-02T00:13:00+00:00",
    )
    store.record_execution(
        failed["closure_id"],
        outcome="failed",
        runtime_source="ha.adapter",
        error="timeout",
        executed_at="2026-04-02T00:14:00+00:00",
    )

    follow_up = store.upsert(
        source="habitus.accepted",
        proposal_id="proposal:follow-up",
        action_id="action:follow-up",
        zone_id="zone:kitchen",
        module_id="light",
        accepted_at="2026-04-02T00:15:00+00:00",
    )
    store.record_execution(
        follow_up["closure_id"],
        outcome="failed",
        runtime_source="ha.adapter",
        error="delivery pending",
        executed_at="2026-04-02T00:16:00+00:00",
    )

    settled = store.upsert(
        source="voice.accepted",
        proposal_id="proposal:settled",
        action_id="action:settled",
        zone_id="zone:hall",
        module_id="notify",
        accepted_at="2026-04-02T00:17:00+00:00",
    )
    store.record_execution(
        settled["closure_id"],
        outcome="failed",
        runtime_source="ha.adapter",
        error="manual follow-up required",
        executed_at="2026-04-02T00:18:00+00:00",
    )

    dispatch_index = _build_dispatch_index()
    app = Flask(__name__)

    with app.test_request_context(
        "/notifications/action-closures/dispatch/receipt",
        method="POST",
        json={
            "dispatch_id": dispatch_index[follow_up["closure_id"]]["dispatch_id"],
            "receipt_state": "failed",
            "receipt_by": "worker.notifications",
            "retry_state": "scheduled",
            "retry_count": 1,
        },
    ):
        record_action_closure_follow_up_receipt()

    with app.test_request_context(
        "/notifications/action-closures/dispatch/claim",
        method="POST",
        json={
            "dispatch_id": dispatch_index[settled["closure_id"]]["dispatch_id"],
            "claimed_by": "worker.notifications",
            "lease_seconds": 300,
        },
    ):
        claim_action_closure_follow_up_dispatch()

    with app.test_request_context(
        "/notifications/action-closures/dispatch/receipt",
        method="POST",
        json={
            "dispatch_id": dispatch_index[settled["closure_id"]]["dispatch_id"],
            "receipt_state": "delivered",
            "receipt_by": "worker.notifications",
        },
    ):
        record_action_closure_follow_up_receipt()

    with app.test_request_context(
        "/notifications/action-closures/dispatch/settle",
        method="POST",
        json={
            "dispatch_id": dispatch_index[settled["closure_id"]]["dispatch_id"],
            "settlement_state": "settled",
            "settled_by": "worker.notifications",
            "note": "resolved",
        },
    ):
        settle_action_closure_follow_up_dispatch()

    return {
        "accepted": accepted["proposal_id"],
        "executed": executed["proposal_id"],
        "failed": failed["proposal_id"],
        "follow_up": follow_up["proposal_id"],
        "settled": settled["proposal_id"],
    }


def test_proposal_lifecycle_status_summary_materializes_canonical_statuses() -> None:
    proposal_ids = _seed_statuses()
    engine = AutomationSuggestionEngine()
    suggestion = engine.suggest_from_presence(away_minutes=45)
    suggested_payload = engine.accept_suggestion(suggestion.id)
    assert suggested_payload is not None

    summary = build_proposal_lifecycle_status_summary(
        get_action_closure_store(),
        proposal_provider=engine,
        recent_limit=10,
    ).to_dict()

    assert summary["contract"] == "ProposalLifecycleStatusSummaryV1"
    assert summary["total_proposals"] == 6
    assert summary["lifecycle_statuses"]["suggested"] == 1
    assert summary["lifecycle_statuses"]["accepted"] == 1
    assert summary["lifecycle_statuses"]["executed"] == 1
    assert summary["lifecycle_statuses"]["failed"] == 1
    assert summary["lifecycle_statuses"]["follow_up_open"] == 1
    assert summary["lifecycle_statuses"]["settled"] == 1
    assert summary["delta"]["current_revision"] >= summary["revision"] - 0

    assert get_proposal_lifecycle_status(proposal_ids["accepted"], store=get_action_closure_store()).to_dict()["lifecycle_status"] == "accepted"
    assert get_proposal_lifecycle_status(proposal_ids["executed"], store=get_action_closure_store()).to_dict()["lifecycle_status"] == "executed"
    assert get_proposal_lifecycle_status(proposal_ids["failed"], store=get_action_closure_store()).to_dict()["lifecycle_status"] == "failed"
    assert get_proposal_lifecycle_status(proposal_ids["follow_up"], store=get_action_closure_store()).to_dict()["lifecycle_status"] == "follow_up_open"
    assert get_proposal_lifecycle_status(proposal_ids["settled"], store=get_action_closure_store()).to_dict()["lifecycle_status"] == "settled"
    assert get_proposal_lifecycle_status(
        suggested_payload["proposal_id"],
        store=get_action_closure_store(),
        proposal_provider=engine,
    ).to_dict()["lifecycle_status"] == "suggested"


def test_proposals_status_api_uses_correct_prefix_and_detail_surface(monkeypatch) -> None:
    engine = AutomationSuggestionEngine()
    suggestion = engine.suggest_from_presence(away_minutes=30)
    proposal = engine.accept_suggestion(suggestion.id)
    assert proposal is not None

    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    app = Flask(__name__)
    init_proposals_api(engine)
    app.register_blueprint(proposals_bp)
    client = app.test_client()
    headers = {"Authorization": "Bearer test-token"}

    list_response = client.get("/api/v1/proposals")
    assert list_response.status_code == 200
    assert list_response.get_json()["count"] == 1

    detail_response = client.get(f"/api/v1/proposals/{proposal['proposal_id']}")
    assert detail_response.status_code == 200
    assert detail_response.get_json()["proposal"]["proposal_id"] == proposal["proposal_id"]

    summary_response = client.get("/api/v1/proposals/status?recent_limit=5", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.get_json()["summary"]
    assert summary["contract"] == "ProposalLifecycleStatusSummaryV1"
    assert summary["lifecycle_statuses"]["suggested"] == 1

    status_response = client.get(f"/api/v1/proposals/{proposal['proposal_id']}/status", headers=headers)
    assert status_response.status_code == 200
    status = status_response.get_json()["status"]
    assert status["contract"] == "ProposalLifecycleStatusV1"
    assert status["proposal_id"] == proposal["proposal_id"]
    assert status["lifecycle_status"] == "suggested"


def test_zone_dashboard_and_chat_surface_proposal_lifecycle_summary() -> None:
    _seed_statuses()
    engine = AutomationSuggestionEngine()
    suggestion = engine.suggest_from_presence(away_minutes=20)
    engine.accept_suggestion(suggestion.id)
    init_zone_dashboard_api(suggestion_engine=engine)

    ctx = _build_global_context()
    assert ctx["proposal_lifecycle"]["total"] == 6
    assert ctx["proposal_lifecycle"]["statuses"]["follow_up_open"] == 1
    assert ctx["proposal_lifecycle"]["statuses"]["settled"] == 1
    assert ctx["proposal_lifecycle"]["recent"]

    app = Flask(__name__)
    app.config["COPILOT_SERVICES"] = {"suggestion_engine": engine}
    with app.app_context():
        handler = ChatHandler()
        home_context = handler._build_home_context()

    assert "Proposal-Lifecycle" in home_context
    assert "follow-up-open" in home_context
