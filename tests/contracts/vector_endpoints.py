"""
Pact-Style Contract Tests for Vector Endpoints.

Consumer-driven contracts for API response validation.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import hashlib
import json

_LOGGER = logging.getLogger(__name__)


@dataclass
class ContractResponse:
    """Expected API response format."""
    status_code: int
    schema: Dict[str, Any]
    headers: Optional[Dict[str, str]] = None


@dataclass
class PactContract:
    """Pact contract for consumer-provider interaction."""
    consumer: str
    provider: str
    interactions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_interaction(
        self,
        description: str,
        request: Dict[str, Any],
        response: ContractResponse,
    ) -> None:
        """Add an interaction to the contract."""
        self.interactions.append({
            "description": description,
            "request": request,
            "response": {
                "status": response.status_code,
                "headers": response.headers or {},
                "body": response.schema,
            },
        })

    def to_dict(self) -> Dict[str, Any]:
        """Export contract as dict."""
        return {
            "consumer": {"name": self.consumer},
            "provider": {"name": self.provider},
            "interactions": self.interactions,
            "metadata": self.metadata,
        }

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of contract."""
        contract_json = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(contract_json.encode()).hexdigest()[:16]


class VectorEndpointContracts:
    """Contract definitions for Vector endpoints."""

    SEARCH_CONTRACT = ContractResponse(
        status_code=200,
        schema={
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "score": {"type": "number"},
                            "metadata": {"type": "object"},
                        },
                    },
                },
                "total": {"type": "integer"},
                "query": {"type": "string"},
            },
        },
    )

    UPSERT_CONTRACT = ContractResponse(
        status_code=200,
        schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "status": {"type": "string"},
                "chunk_count": {"type": "integer"},
            },
        },
    )

    DELETE_CONTRACT = ContractResponse(
        status_code=200,
        schema={
            "type": "object",
            "properties": {
                "deleted": {"type": "boolean"},
                "id": {"type": "string"},
            },
        },
    )


def validate_response_contract(
    response_data: Dict[str, Any],
    contract: ContractResponse,
) -> bool:
    """Validate response against contract schema."""
    # Basic validation - in production use jsonschema
    if contract.status_code != 200:
        return False
    
    required_keys = set(contract.schema.get("properties", {}).keys())
    actual_keys = set(response_data.keys())
    
    # Check required properties exist
    if not required_keys.issubset(actual_keys):
        missing = required_keys - actual_keys
        _LOGGER.warning("Contract violation: missing keys %s", missing)
        return False
    
    return True


__all__ = [
    "ContractResponse",
    "PactContract",
    "VectorEndpointContracts",
    "validate_response_contract",
]
