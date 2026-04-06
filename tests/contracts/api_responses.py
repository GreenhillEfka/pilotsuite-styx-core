"""
API Response Format Contracts.

Contract validation for all API endpoints.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass
from enum import Enum

_LOGGER = logging.getLogger(__name__)


class ResponseStatus(Enum):
    """API response status codes."""
    SUCCESS = 200
    CREATED = 201
    BAD_REQUEST = 400
    NOT_FOUND = 404
    INTERNAL_ERROR = 500


@dataclass
class APIResponseContract:
    """Contract for API response format."""
    endpoint: str
    method: str
    status: ResponseStatus
    schema: Dict[str, Any]
    required_fields: List[str]
    optional_fields: Optional[List[str]] = None


class ResponseValidator:
    """Validates API responses against contracts."""

    def __init__(self) -> None:
        """Initialize validator."""
        self._contracts: Dict[str, APIResponseContract] = {}
        self._register_default_contracts()

    def _register_default_contracts(self) -> None:
        """Register default API contracts."""
        # Analytics endpoints
        self.register(APIResponseContract(
            endpoint="/api/v1/analytics/overview",
            method="GET",
            status=ResponseStatus.SUCCESS,
            schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "modules": {"type": "array"},
                    "kpis": {"type": "object"},
                },
            },
            required_fields=["status", "modules", "kpis"],
        ))

        # Calendar endpoints
        self.register(APIResponseContract(
            endpoint="/api/v1/calendar/events",
            method="GET",
            status=ResponseStatus.SUCCESS,
            schema={
                "type": "object",
                "properties": {
                    "events": {"type": "array"},
                    "count": {"type": "integer"},
                },
            },
            required_fields=["events", "count"],
        ))

        # Presence endpoints
        self.register(APIResponseContract(
            endpoint="/api/v1/presence/status",
            method="GET",
            status=ResponseStatus.SUCCESS,
            schema={
                "type": "object",
                "properties": {
                    "zones": {"type": "object"},
                    "timestamp": {"type": "string"},
                },
            },
            required_fields=["zones", "timestamp"],
        ))

    def register(self, contract: APIResponseContract) -> None:
        """Register a contract."""
        key = f"{contract.method}:{contract.endpoint}"
        self._contracts[key] = contract
        _LOGGER.debug("Registered contract: %s", key)

    def validate(
        self,
        endpoint: str,
        method: str,
        response_data: Dict[str, Any],
    ) -> bool:
        """Validate response against registered contract."""
        key = f"{method}:{endpoint}"
        contract = self._contracts.get(key)

        if not contract:
            _LOGGER.warning("No contract found for %s", key)
            return True  # No contract = pass

        # Check status
        # In real validation, check response status code

        # Check required fields
        for field in contract.required_fields:
            if field not in response_data:
                _LOGGER.error("Contract violation [%s]: missing field '%s'", key, field)
                return False

        return True


# Global validator instance
_response_validator: Optional[ResponseValidator] = None


def get_response_validator() -> ResponseValidator:
    """Get global response validator."""
    global _response_validator
    if _response_validator is None:
        _response_validator = ResponseValidator()
    return _response_validator


__all__ = [
    "ResponseStatus",
    "APIResponseContract",
    "ResponseValidator",
    "get_response_validator",
]
