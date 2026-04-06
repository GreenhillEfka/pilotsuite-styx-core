"""API Endpoint Contract Schema (E1).

Pydantic v2-based schema for API endpoint definitions, request/response validation,
and OpenAPI specification generation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class HttpMethod(str, Enum):
    """HTTP methods supported by API endpoints."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


class AuthRequirement(str, Enum):
    """Authentication requirements for endpoints."""
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"
    ADMIN = "admin"


class ParameterLocation(str, Enum):
    """Location of request parameters."""
    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    BODY = "body"


class ParameterSchema(BaseModel):
    """Schema for a single API parameter."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=128)
    location: ParameterLocation
    type: Literal["string", "integer", "number", "boolean", "array", "object"]
    description: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    pattern: Optional[str] = None
    enum: Optional[List[Any]] = None
    example: Optional[Any] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Parameter name must be alphanumeric (underscores/hyphens allowed)")
        return v


class ResponseSchema(BaseModel):
    """Schema for API response definition."""
    model_config = ConfigDict(extra="forbid")

    status_code: int = Field(..., ge=100, lt=600)
    description: str = Field(..., min_length=1, max_length=1024)
    content_type: str = Field(default="application/json")
    schema_ref: Optional[str] = Field(None, description="Reference to response schema")
    example: Optional[Dict[str, Any]] = None


class RateLimitConfig(BaseModel):
    """Rate limiting configuration for an endpoint."""
    model_config = ConfigDict(extra="forbid")

    requests_per_minute: Optional[int] = Field(None, ge=1)
    requests_per_hour: Optional[int] = Field(None, ge=1)
    requests_per_day: Optional[int] = Field(None, ge=1)
    burst_limit: Optional[int] = Field(None, ge=1)

    @model_validator(mode="after")
    def validate_limits(self) -> "RateLimitConfig":
        if not any([
            self.requests_per_minute,
            self.requests_per_hour,
            self.requests_per_day,
        ]):
            raise ValueError("At least one rate limit must be specified")
        return self


class EndpointContract(BaseModel):
    """Contract definition for a single API endpoint."""
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    # === Identity ===
    endpoint_id: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Unique endpoint identifier",
        examples=["get_zone_status", "create_automation"],
    )
    path: str = Field(
        ...,
        pattern=r"^/.*$",
        description="URL path pattern (may include path parameters like {id})",
        examples=["/api/v1/zones/{zone_id}/status"],
    )
    method: HttpMethod
    summary: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = Field(None, max_length=4096)
    tags: List[str] = Field(default_factory=list)

    # === Parameters ===
    parameters: List[ParameterSchema] = Field(default_factory=list)
    request_body_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="JSON Schema for request body (for POST/PUT/PATCH)",
    )

    # === Responses ===
    responses: List[ResponseSchema] = Field(
        default_factory=list,
        description="Possible response definitions",
    )

    # === Security ===
    auth_requirement: AuthRequirement = Field(default=AuthRequirement.REQUIRED)
    permissions: List[str] = Field(
        default_factory=list,
        description="Required permission scopes",
    )

    # === Rate Limiting ===
    rate_limit: Optional[RateLimitConfig] = None

    # === Metadata ===
    version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
    )
    deprecated: bool = False
    deprecation_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # === Validation ===
    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v: List[ParameterSchema]) -> List[ParameterSchema]:
        names = set()
        for param in v:
            if param.name in names:
                raise ValueError(f"Duplicate parameter name: {param.name}")
            names.add(param.name)
            if param.location == ParameterLocation.PATH and not param.required:
                raise ValueError(f"Path parameter '{param.name}' must be required")
        return v

    @field_validator("responses")
    @classmethod
    def validate_responses(cls, v: List[ResponseSchema]) -> List[ResponseSchema]:
        if not v:
            raise ValueError("At least one response must be defined")
        status_codes = set()
        for resp in v:
            if resp.status_code in status_codes:
                raise ValueError(f"Duplicate status code: {resp.status_code}")
            status_codes.add(resp.status_code)
        return v

    @model_validator(mode="after")
    def validate_request_body_for_method(self) -> "EndpointContract":
        if self.method in ("POST", "PUT", "PATCH") and not self.request_body_schema:
            # Not an error, but worth noting
            pass
        if self.method in ("GET", "DELETE", "HEAD", "OPTIONS") and self.request_body_schema:
            raise ValueError(f"{self.method} methods should not have request body schema")
        return self

    def compute_hash(self) -> str:
        """Compute deterministic SHA-256 hash of endpoint signature."""
        signature = {
            "endpoint_id": self.endpoint_id,
            "path": self.path,
            "method": self.method.value,
            "parameters": [p.model_dump() for p in self.parameters],
            "request_body_schema": self.request_body_schema,
            "responses": [r.model_dump() for r in self.responses],
            "auth_requirement": self.auth_requirement.value,
        }
        dump = json.dumps(signature, sort_keys=True, default=str)
        return hashlib.sha256(dump.encode()).hexdigest()

    def to_openapi_operation(self) -> Dict[str, Any]:
        """Convert to OpenAPI 3.1 operation object."""
        operation: Dict[str, Any] = {
            "operationId": self.endpoint_id,
            "summary": self.summary,
            "tags": self.tags,
            "parameters": [],
            "responses": {},
        }

        if self.description:
            operation["description"] = self.description

        # Parameters
        for param in self.parameters:
            param_obj: Dict[str, Any] = {
                "name": param.name,
                "in": param.location.value,
                "required": param.required,
                "schema": {
                    "type": param.type,
                },
            }
            if param.description:
                param_obj["description"] = param.description
            if param.default is not None:
                param_obj["schema"]["default"] = param.default
            if param.minimum is not None:
                param_obj["schema"]["minimum"] = param.minimum
            if param.maximum is not None:
                param_obj["schema"]["maximum"] = param.maximum
            if param.pattern:
                param_obj["schema"]["pattern"] = param.pattern
            if param.enum:
                param_obj["schema"]["enum"] = param.enum
            if param.example is not None:
                param_obj["example"] = param.example
            operation["parameters"].append(param_obj)

        # Request body
        if self.request_body_schema:
            operation["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": self.request_body_schema,
                    },
                },
            }

        # Responses
        for resp in self.responses:
            resp_obj: Dict[str, Any] = {
                "description": resp.description,
            }
            if resp.example:
                resp_obj["content"] = {
                    resp.content_type: {
                        "example": resp.example,
                    },
                }
            operation["responses"][str(resp.status_code)] = resp_obj

        # Security
        if self.auth_requirement != AuthRequirement.NONE:
            security_scheme = "bearerAuth" if self.auth_requirement == AuthRequirement.ADMIN else "apiToken"
            operation["security"] = [{security_scheme: self.permissions}]

        # Deprecation
        if self.deprecated:
            operation["deprecated"] = True

        return operation


class ApiContract(BaseModel):
    """Complete API contract containing multiple endpoints."""
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    api_id: str = Field(..., pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(..., min_length=1, max_length=256)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    base_path: str = Field(..., pattern=r"^/.*$")
    description: Optional[str] = None
    endpoints: List[EndpointContract] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def compute_hash(self) -> str:
        """Compute deterministic SHA-256 hash of API signature."""
        signature = {
            "api_id": self.api_id,
            "version": self.version,
            "endpoints": [e.compute_hash() for e in self.endpoints],
        }
        dump = json.dumps(signature, sort_keys=True, default=str)
        return hashlib.sha256(dump.encode()).hexdigest()

    def to_openapi_spec(self) -> Dict[str, Any]:
        """Generate complete OpenAPI 3.1 specification."""
        spec: Dict[str, Any] = {
            "openapi": "3.1.0",
            "info": {
                "title": self.name,
                "version": self.version,
                "description": self.description,
            },
            "paths": {},
            "components": {
                "securitySchemes": {
                    "apiToken": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-Auth-Token",
                    },
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                    },
                },
            },
        }

        for endpoint in self.endpoints:
            if endpoint.path not in spec["paths"]:
                spec["paths"][endpoint.path] = {}
            spec["paths"][endpoint.path][endpoint.method.value.lower()] = endpoint.to_openapi_operation()

        return spec


# === Example ===
EXAMPLE_API = ApiContract(
    api_id="zone-automation",
    name="Zone Automation API",
    version="1.0.0",
    base_path="/api/v1/zone-automation",
    description="API for managing zone-based automations",
    endpoints=[
        EndpointContract(
            endpoint_id="get_zone_status",
            path="/api/v1/zone-automation/{zone_id}/status",
            method=HttpMethod.GET,
            summary="Get zone automation status",
            parameters=[
                ParameterSchema(
                    name="zone_id",
                    location=ParameterLocation.PATH,
                    type="string",
                    description="Zone identifier",
                    required=True,
                ),
            ],
            responses=[
                ResponseSchema(
                    status_code=200,
                    description="Zone status retrieved successfully",
                    example={"zone_id": "living_room", "active": True},
                ),
                ResponseSchema(
                    status_code=404,
                    description="Zone not found",
                ),
            ],
            auth_requirement=AuthRequirement.REQUIRED,
        ),
    ],
)
