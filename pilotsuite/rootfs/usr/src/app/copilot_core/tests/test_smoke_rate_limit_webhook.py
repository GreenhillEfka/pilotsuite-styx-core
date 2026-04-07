"""Smoke tests for rate limit + webhook delivery consistency (PS-QA-031)."""
from __future__ import annotations

import io
import urllib.error

from flask import Flask

from copilot_core.api.middleware.rate_limit import rate_limit_exceeded_response
from copilot_core.models.rate_limit import RateLimitConfig, TokenBucket
from copilot_core.webhook_delivery import WebhookDeliveryQueue


def _build_rate_limit_response():
    app = Flask(__name__)
    config = RateLimitConfig(requests_per_minute=60, burst_size=1)
    bucket = TokenBucket.from_config(config)
    bucket.tokens = 0
    with app.app_context():
        response = rate_limit_exceeded_response(config, bucket)
    return response, config


def test_rate_limit_429_response_contract_is_deterministic():
    response, config = _build_rate_limit_response()

    body = response.get_json()
    assert response.status_code == 429
    assert body["error"] == "rate_limit_exceeded"
    assert body["retry_after"] == body["retry_after_seconds"]
    assert body["limit"] == config.requests_per_minute
    assert response.headers["Retry-After"] == str(body["retry_after"])


def test_rate_limit_429_is_fail_fast_in_webhook_delivery_stats():
    response, _ = _build_rate_limit_response()
    body_bytes = response.get_data()
    headers = response.headers

    def _send(_envelope):
        raise urllib.error.HTTPError(
            url="http://example.test/hook",
            code=429,
            msg="Too Many Requests",
            hdrs=headers,
            fp=io.BytesIO(body_bytes),
        )

    queue = WebhookDeliveryQueue(
        send_func=_send,
        worker_count=1,
        max_queue_size=4,
        max_retries=2,
        retry_base_delay_seconds=0.0,
        retry_jitter_seconds=0.0,
    )
    queue.start()

    assert queue.enqueue({"type": "status", "data": {"ok": True}}) is True

    queue.stop(drain_timeout=1.0)

    stats = queue._get_stats_snapshot()
    assert stats["delivered_total"] == 0
    assert stats["failed_total"] == 1
    assert stats["retry_total"] == 0
