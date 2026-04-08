"""Pydantic validation decorator for Flask route handlers."""
from __future__ import annotations

import functools
import logging
from typing import Type

from flask import jsonify, request
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


def validate_json(model: Type[BaseModel]):
    """Decorator that auto-parses and validates the JSON request body.

    Usage::

        @bp.post("/endpoint")
        @validate_json(MyModel)
        def handle(body: MyModel):
            ...

    On validation failure returns 400 with structured error details.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            raw = request.get_json(silent=True)
            if raw is None:
                return jsonify({
                    "ok": False,
                    "error": "invalid_json",
                    "detail": "Request body must be valid JSON",
                }), 400

            if not isinstance(raw, dict):
                return jsonify({
                    "ok": False,
                    "error": "invalid_json",
                    "detail": "Request body must be a JSON object",
                }), 400

            try:
                body = model.model_validate(raw)
            except ValidationError as exc:
                errors = []
                for err in exc.errors():
                    errors.append({
                        "field": ".".join(str(loc) for loc in err["loc"]),
                        "message": err["msg"],
                        "type": err["type"],
                    })
                return jsonify({
                    "ok": False,
                    "error": "validation_error",
                    "detail": errors,
                }), 400

            return fn(body, *args, **kwargs)

        return wrapper

    return decorator
