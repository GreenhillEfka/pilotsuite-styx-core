"""P5-001: REST API Completion — OpenAPI 3.0, Versioning, All Endpoints."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class APIVersion(Enum):
    """API versions."""
    V1 = "v1"
    V2 = "v2"


@dataclass
class APIEndpoint:
    """API endpoint definition."""
    path: str
    method: str
    description: str
    tags: List[str] = field(default_factory=list)
    request_schema: Optional[Dict] = None
    response_schema: Optional[Dict] = None
    requires_auth: bool = True


@dataclass
class OpenAPISpec:
    """OpenAPI specification generator."""
    title: str
    version: str
    description: str
    endpoints: List[APIEndpoint] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to OpenAPI 3.0 dict."""
        paths = {}
        for endpoint in self.endpoints:
            if endpoint.path not in paths:
                paths[endpoint.path] = {}
            
            paths[endpoint.path][endpoint.method.lower()] = {
                "summary": endpoint.description,
                "tags": endpoint.tags,
                "operationId": f"{endpoint.method.lower()}_{endpoint.path.replace('/', '_').replace('{', '').replace('}', '')}",
                "security": [{"bearerAuth": []}] if endpoint.requires_auth else [],
            }
        
        return {
            "openapi": "3.0.0",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": self.description,
            },
            "paths": paths,
            "components": {
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer"}
                }
            }
        }

    def save(self, path: str):
        """Save OpenAPI spec to file."""
        import json
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Saved OpenAPI spec to {path}")


class RESTAPI:
    """Complete REST API with OpenAPI spec."""

    def __init__(self, version: APIVersion = APIVersion.V1):
        self.version = version
        self._endpoints: Dict[str, APIEndpoint] = {}
        self._register_core_endpoints()

    def _register_core_endpoints(self):
        """Register core API endpoints."""
        # Health & Status
        self._register(APIEndpoint("/api/v1/health", "GET", "Health check", ["system"], requires_auth=False))
        self._register(APIEndpoint("/api/v1/status", "GET", "System status", ["system"]))
        
        # RAG Endpoints
        self._register(APIEndpoint("/api/v1/rag/query", "POST", "Query RAG system", ["rag"]))
        self._register(APIEndpoint("/api/v1/rag/documents", "GET", "List documents", ["rag"]))
        self._register(APIEndpoint("/api/v1/rag/documents", "POST", "Add document", ["rag"]))
        self._register(APIEndpoint("/api/v1/rag/memory", "GET", "Query memory", ["rag"]))
        
        # Voice Endpoints
        for path, method, description in (
            ("/api/v1/voice/intent", "POST", "Process voice intent"),
            ("/api/v1/voice/transcribe", "POST", "Transcribe audio"),
            ("/api/v1/voice/synthesize", "POST", "Synthesize speech"),
            ("/api/v1/voice/speak", "POST", "Synthesize speech and return a retrievable audio artifact"),
            ("/api/v1/voice/status", "GET", "Get voice runtime status and safe-call capability truth"),
            ("/api/v1/voice/audio/{audio_id}", "GET", "Retrieve a generated voice audio artifact"),
            ("/api/v1/voice/zones", "GET", "List available voice zones"),
            ("/api/v1/voice/intents", "GET", "List supported voice intents"),
        ):
            self._register(APIEndpoint(path, method, description, ["voice"]))
        
        # ML Endpoints
        self._register(APIEndpoint("/api/v1/ml/patterns", "GET", "Get detected patterns", ["ml"]))
        self._register(APIEndpoint("/api/v1/ml/habits", "GET", "Get habits", ["ml"]))
        self._register(APIEndpoint("/api/v1/ml/anomalies", "GET", "Get anomalies", ["ml"]))
        
        # User Endpoints
        self._register(APIEndpoint("/api/v1/users", "GET", "List users", ["users"]))
        self._register(APIEndpoint("/api/v1/users/{user_id}", "GET", "Get user", ["users"]))
        self._register(APIEndpoint("/api/v1/users/{user_id}/preferences", "GET", "Get preferences", ["users"]))
        
        # Admin Endpoints
        self._register(APIEndpoint("/api/v1/admin/config", "GET", "Get config", ["admin"]))
        self._register(APIEndpoint("/api/v1/admin/config", "PUT", "Update config", ["admin"]))
        self._register(APIEndpoint("/api/v1/admin/stats", "GET", "Get system stats", ["admin"], requires_auth=True))

    def _register(self, endpoint: APIEndpoint):
        """Register an endpoint."""
        key = f"{endpoint.method}:{endpoint.path}"
        self._endpoints[key] = endpoint

    def get_openapi_spec(self) -> OpenAPISpec:
        """Generate OpenAPI specification."""
        spec = OpenAPISpec(
            title="PilotSuite Core API",
            version=self.version.value,
            description="Complete REST API for PilotSuite Core"
        )
        spec.endpoints = list(self._endpoints.values())
        return spec

    def save_openapi_spec(self, path: str):
        """Save OpenAPI spec to file."""
        spec = self.get_openapi_spec()
        spec.save(path)

    def get_endpoints(self, tag: Optional[str] = None) -> List[APIEndpoint]:
        """Get all endpoints (optionally filtered by tag)."""
        endpoints = list(self._endpoints.values())
        if tag:
            endpoints = [e for e in endpoints if tag in e.tags]
        return endpoints

    def get_stats(self) -> Dict[str, Any]:
        """Get API statistics."""
        return {
            "version": self.version.value,
            "total_endpoints": len(self._endpoints),
            "tags": list(set(tag for e in self._endpoints.values() for tag in e.tags)),
        }


# Global default REST API
default_rest_api: Optional[RESTAPI] = None


def init_rest_api(version: APIVersion = APIVersion.V1) -> RESTAPI:
    """Initialize global REST API."""
    global default_rest_api
    default_rest_api = RESTAPI(version)
    return default_rest_api
