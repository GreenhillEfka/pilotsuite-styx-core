"""Webhook Engine — Slice 53.

Webhook delivery for PilotSuite Core.

Features:
- Webhook registration and management
- Event-based triggers
- Delivery with retries
- Signature verification
- Payload transformation
- Delivery logs and statistics
"""
from __future__ import annotations

import logging
import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import uuid
from copy import deepcopy

logger = logging.getLogger(__name__)


class WebhookStatus(Enum):
    """Webhook status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISABLED = "disabled"


class DeliveryStatus(Enum):
    """Delivery status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Webhook:
    """Webhook configuration."""
    webhook_id: str
    name: str
    url: str
    events: List[str]
    status: WebhookStatus = WebhookStatus.ACTIVE
    secret: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30
    max_retries: int = 3
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "webhook_id": self.webhook_id,
            "name": self.name,
            "url": self.url,
            "events": self.events,
            "status": self.status.value,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


@dataclass
class Delivery:
    """Webhook delivery record."""
    delivery_id: str
    webhook_id: str
    event_type: str
    payload: Dict[str, Any]
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempts: int = 0
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    delivered_at: Optional[str] = None
    next_retry_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "webhook_id": self.webhook_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "status": self.status.value,
            "attempts": self.attempts,
            "response_code": self.response_code,
            "response_body": self.response_body,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "delivered_at": self.delivered_at,
            "next_retry_at": self.next_retry_at,
        }


class WebhookEngine:
    """Webhook delivery engine."""
    
    def __init__(self):
        self._webhooks: Dict[str, Webhook] = {}
        self._deliveries: Dict[str, Delivery] = {}
        self._delivery_by_webhook: Dict[str, List[str]] = {}  # webhook_id -> [delivery_ids]
        self._http_client: Optional[Callable] = None
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            "total_deliveries": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "retries": 0,
            "by_event_type": {},
            "by_webhook": {},
        }
    
    def set_http_client(self, client: Callable[[str, Dict[str, Any], Dict[str, str], int], tuple]) -> None:
        """Set HTTP client for testing."""
        self._http_client = client
    
    def register_webhook(self, name: str, url: str,
                        events: List[str],
                        secret: Optional[str] = None,
                        headers: Optional[Dict[str, str]] = None,
                        timeout_seconds: int = 30,
                        max_retries: int = 3,
                        metadata: Optional[Dict[str, Any]] = None) -> str:
        """Register a new webhook."""
        webhook_id = f"wh_{uuid.uuid4().hex[:16]}"
        
        webhook = Webhook(
            webhook_id=webhook_id,
            name=name,
            url=url,
            events=events,
            secret=secret,
            headers=headers or {},
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            metadata=metadata or {},
        )
        
        with self._lock:
            self._webhooks[webhook_id] = webhook
            self._delivery_by_webhook[webhook_id] = []
        
        logger.info("Webhook registered: %s (%s)", name, webhook_id)
        
        return webhook_id
    
    def update_webhook(self, webhook_id: str,
                      name: Optional[str] = None,
                      url: Optional[str] = None,
                      events: Optional[List[str]] = None,
                      status: Optional[WebhookStatus] = None,
                      headers: Optional[Dict[str, str]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update webhook configuration."""
        with self._lock:
            webhook = self._webhooks.get(webhook_id)
            
            if not webhook:
                return False
            
            if name is not None:
                webhook.name = name
            if url is not None:
                webhook.url = url
            if events is not None:
                webhook.events = events
            if status is not None:
                webhook.status = status
            if headers is not None:
                webhook.headers = headers
            if metadata is not None:
                webhook.metadata = metadata
            
            webhook.updated_at = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook."""
        with self._lock:
            if webhook_id not in self._webhooks:
                return False
            
            del self._webhooks[webhook_id]
            del self._delivery_by_webhook[webhook_id]
        
        logger.info("Webhook deleted: %s", webhook_id)
        
        return True
    
    def get_webhook(self, webhook_id: str) -> Optional[Webhook]:
        """Get webhook by ID."""
        webhook = self._webhooks.get(webhook_id)
        return deepcopy(webhook) if webhook is not None else None
    
    def list_webhooks(self, status: Optional[WebhookStatus] = None) -> List[Webhook]:
        """List all webhooks."""
        with self._lock:
            webhooks = list(self._webhooks.values())
            
            if status:
                webhooks = [w for w in webhooks if w.status == status]
            
            return deepcopy(webhooks)
    
    def trigger_event(self, event_type: str, payload: Dict[str, Any]) -> List[str]:
        """Trigger event and deliver to matching webhooks."""
        delivery_ids = []
        
        with self._lock:
            for webhook in self._webhooks.values():
                if webhook.status != WebhookStatus.ACTIVE:
                    continue
                
                if event_type not in webhook.events and "*" not in webhook.events:
                    continue
                
                # Create delivery
                delivery_id = self._create_delivery(webhook.webhook_id, event_type, payload)
                delivery_ids.append(delivery_id)
        
        # Process deliveries
        for delivery_id in delivery_ids:
            self._process_delivery(delivery_id)
        
        return delivery_ids
    
    def _create_delivery(self, webhook_id: str, event_type: str,
                        payload: Dict[str, Any]) -> str:
        """Create a delivery record."""
        delivery_id = f"del_{uuid.uuid4().hex[:16]}"
        
        delivery = Delivery(
            delivery_id=delivery_id,
            webhook_id=webhook_id,
            event_type=event_type,
            payload=payload,
        )
        
        with self._lock:
            self._deliveries[delivery_id] = delivery
            self._delivery_by_webhook[webhook_id].append(delivery_id)
            
            self._stats["total_deliveries"] += 1
            self._stats["by_event_type"][event_type] = \
                self._stats["by_event_type"].get(event_type, 0) + 1
        
        return delivery_id
    
    def _process_delivery(self, delivery_id: str) -> None:
        """Process a delivery."""
        with self._lock:
            delivery = self._deliveries.get(delivery_id)
            
            if not delivery:
                return
            
            webhook = self._webhooks.get(delivery.webhook_id)
            
            if not webhook:
                delivery.status = DeliveryStatus.FAILED
                delivery.error_message = "Webhook not found"
                return
            
            delivery.status = DeliveryStatus.PENDING
            delivery.attempts += 1
        
        # Build request
        payload_json = json.dumps(delivery.payload)
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": delivery.event_type,
            "X-Webhook-Delivery-ID": delivery_id,
            **webhook.headers,
        }
        
        # Add signature if secret configured
        if webhook.secret:
            signature = self._generate_signature(payload_json, webhook.secret)
            headers["X-Webhook-Signature"] = signature
        
        # Execute HTTP request
        success = False
        error = None
        response_code = None
        response_body = None
        
        try:
            if self._http_client:
                # Use test client
                response_code, response_body = self._http_client(
                    webhook.url,
                    delivery.payload,
                    headers,
                    webhook.timeout_seconds,
                )
            else:
                # Simulate delivery (for testing without real HTTP)
                response_code = 200
                response_body = '{"status": "ok"}'
            
            if response_code and 200 <= response_code < 300:
                success = True
            else:
                error = f"HTTP {response_code}"
                
        except Exception as e:
            error = str(e)
        
        # Update delivery
        with self._lock:
            delivery.response_code = response_code
            delivery.response_body = response_body
            
            if success:
                delivery.status = DeliveryStatus.DELIVERED
                delivery.delivered_at = datetime.now(timezone.utc).isoformat()
                
                self._stats["successful_deliveries"] += 1
                self._stats["by_webhook"][webhook.webhook_id] = \
                    self._stats["by_webhook"].get(webhook.webhook_id, 0) + 1
                
                logger.debug("Delivery successful: %s", delivery_id)
            else:
                delivery.error_message = error
                
                if delivery.attempts < webhook.max_retries:
                    delivery.status = DeliveryStatus.RETRYING
                    # Schedule retry with backoff metadata, but execute the retry
                    # immediately in-process for deterministic test/runtime behavior.
                    backoff_seconds = min(300, 2 ** delivery.attempts * 10)
                    delivery.next_retry_at = (
                        datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
                    ).isoformat()
                    
                    self._stats["retries"] += 1
                    
                    logger.warning("Delivery failed, scheduling retry: %s (attempt %d)",
                                  delivery_id, delivery.attempts)
                else:
                    delivery.status = DeliveryStatus.FAILED
                    
                    self._stats["failed_deliveries"] += 1
                    
                    logger.error("Delivery failed permanently: %s", delivery_id)

        if self._deliveries[delivery_id].status == DeliveryStatus.RETRYING:
            self._process_delivery(delivery_id)
    
    def _generate_signature(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for payload."""
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        return f"sha256={signature}"
    
    def verify_signature(self, payload: str, signature: str, secret: str) -> bool:
        """Verify webhook signature."""
        expected = self._generate_signature(payload, secret)
        
        return hmac.compare_digest(expected, signature)
    
    def get_delivery(self, delivery_id: str) -> Optional[Delivery]:
        """Get delivery by ID."""
        return self._deliveries.get(delivery_id)
    
    def list_deliveries(self, webhook_id: Optional[str] = None,
                       status: Optional[DeliveryStatus] = None,
                       limit: int = 100) -> List[Delivery]:
        """List deliveries with filters."""
        with self._lock:
            if webhook_id:
                delivery_ids = self._delivery_by_webhook.get(webhook_id, [])
                deliveries = [
                    self._deliveries[did]
                    for did in delivery_ids
                    if did in self._deliveries
                ]
            else:
                deliveries = list(self._deliveries.values())
            
            if status:
                deliveries = [d for d in deliveries if d.status == status]
            
            # Sort by created_at descending
            deliveries.sort(key=lambda d: d.created_at, reverse=True)
            
            return deliveries[:limit]
    
    def retry_delivery(self, delivery_id: str) -> bool:
        """Manually retry a failed delivery."""
        with self._lock:
            delivery = self._deliveries.get(delivery_id)
            
            if not delivery:
                return False
            
            if delivery.status not in (DeliveryStatus.FAILED, DeliveryStatus.RETRYING):
                return False
            
            # Reset for retry
            delivery.status = DeliveryStatus.PENDING
            delivery.next_retry_at = None
            delivery.error_message = None
        
        self._process_delivery(delivery_id)
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get webhook statistics."""
        with self._lock:
            return {
                **self._stats,
                "total_webhooks": len(self._webhooks),
                "active_webhooks": len([w for w in self._webhooks.values() if w.status == WebhookStatus.ACTIVE]),
                "pending_deliveries": len([d for d in self._deliveries.values() if d.status == DeliveryStatus.PENDING]),
                "retrying_deliveries": len([d for d in self._deliveries.values() if d.status == DeliveryStatus.RETRYING]),
            }
    
    def clear_deliveries(self, webhook_id: Optional[str] = None,
                        older_than_days: Optional[int] = None) -> int:
        """Clear delivery records."""
        with self._lock:
            if webhook_id:
                delivery_ids = self._delivery_by_webhook.get(webhook_id, [])
            else:
                delivery_ids = list(self._deliveries.keys())
            
            cleared = 0
            
            if older_than_days:
                cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
                cutoff_str = cutoff.isoformat()
                
                for delivery_id in delivery_ids:
                    delivery = self._deliveries.get(delivery_id)
                    if delivery and delivery.created_at < cutoff_str:
                        del self._deliveries[delivery_id]
                        cleared += 1
            else:
                for delivery_id in delivery_ids:
                    if delivery_id in self._deliveries:
                        del self._deliveries[delivery_id]
                        cleared += 1
            
            # Clean up delivery_by_webhook
            if webhook_id and webhook_id in self._delivery_by_webhook:
                self._delivery_by_webhook[webhook_id] = [
                    did for did in self._delivery_by_webhook[webhook_id]
                    if did in self._deliveries
                ]
            
            return cleared


def create_webhook_engine() -> WebhookEngine:
    """Factory function to create webhook engine."""
    return WebhookEngine()
