"""Shared API error response models."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standardized API error payload."""

    code: str = Field(..., description="Stable machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    field: Optional[str] = Field(None, description="Optional field name tied to the error")
    context: Optional[Dict[str, Any]] = Field(None, description="Optional structured context")


def error_response_payload(
    code: str,
    message: str,
    *,
    field: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a serialized ErrorResponse payload."""

    model = ErrorResponse(code=code, message=message, field=field, context=context)
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)
