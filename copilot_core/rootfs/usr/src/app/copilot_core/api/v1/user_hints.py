"""User Hints API Blueprint."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from flask import Blueprint, jsonify, request

from .models import HintStatus, HintType
from .service import UserHintsService


_LOGGER = logging.getLogger(__name__)


def _run_async(coro, timeout: int = 10):
    """Run async coroutine from sync Flask context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, asyncio.wait_for(coro, timeout=timeout))
            return future.result(timeout=timeout + 2)

    return asyncio.run(asyncio.wait_for(coro, timeout=timeout))


bp = Blueprint("user_hints", __name__, url_prefix="/hints")
user_hints_bp = bp

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify(
            {
                "ok": False,
                "error": "Authentication required",
                "message": "Valid X-Auth-Token header or Bearer token required",
            }
        ), 401


# Global service instance
_hints_service: UserHintsService | None = None


def init_hints_service(service: UserHintsService | None) -> None:
    """Initialize the hints service."""
    global _hints_service
    _hints_service = service


def get_hints_service() -> UserHintsService:
    """Get the hints service, auto-wiring AutomationCreator if available."""
    global _hints_service
    if _hints_service is None:
        automation_creator = None
        try:
            from flask import current_app

            services = current_app.config.get("COPILOT_SERVICES", {})
            automation_creator = services.get("automation_creator")
        except Exception:
            pass
        _hints_service = UserHintsService(automation_creator=automation_creator)
    return _hints_service


def _error(message: str, status_code: int):
    return jsonify({"ok": False, "error": message}), status_code


def _required_json_object():
    body = request.get_json(silent=True)
    if body is None:
        return None, _error("No JSON body provided", 400)
    if not isinstance(body, dict):
        return None, _error("JSON body must be an object", 400)
    return body, None


def _optional_json_object():
    body = request.get_json(silent=True)
    if body is None:
        return {}, None
    if not isinstance(body, dict):
        return None, _error("JSON body must be an object", 400)
    return body, None


def _parse_optional_enum(raw_value: Any, enum_cls, *, field_name: str, valid_values_key: str | None = None):
    if raw_value is None:
        return None, None
    if not isinstance(raw_value, str):
        return None, _error(f"{field_name} must be a string", 400)

    normalized = raw_value.strip()
    try:
        return enum_cls(normalized), None
    except ValueError:
        payload = {
            "ok": False,
            "error": f"Invalid {field_name}: {raw_value}",
            valid_values_key or f"valid_{field_name}s": [item.value for item in enum_cls],
        }
        return None, (jsonify(payload), 400)


def _parse_optional_string(raw_value: Any, *, field_name: str):
    if raw_value is None:
        return None, None
    if not isinstance(raw_value, str):
        return None, _error(f"{field_name} must be a string", 400)
    return raw_value.strip(), None


@bp.route("", methods=["GET"])
def list_hints():
    """List all hints."""
    try:
        service = get_hints_service()
        status, error_response = _parse_optional_enum(
            request.args.get("status"),
            HintStatus,
            field_name="status",
            valid_values_key="valid_statuses",
        )
        if error_response:
            return error_response

        hints = service.get_hints(status=status)
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to list user hints")
        return _error(str(exc), 500)

    return jsonify(
        {
            "ok": True,
            "hints": [hint.to_dict() for hint in hints],
            "count": len(hints),
        }
    )


@bp.route("", methods=["POST"])
def add_hint():
    """Add a new user hint."""
    body, error_response = _required_json_object()
    if error_response:
        return error_response

    text, error_response = _parse_optional_string(body.get("text"), field_name="text")
    if error_response:
        return error_response
    if not text:
        return _error("Missing 'text' field", 400)

    hint_type, error_response = _parse_optional_enum(
        body.get("type"),
        HintType,
        field_name="type",
        valid_values_key="valid_types",
    )
    if error_response:
        return error_response

    try:
        service = get_hints_service()
        hint = _run_async(service.add_hint(text, hint_type))
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to add user hint")
        return _error(str(exc), 500)

    return jsonify({"ok": True, "hint": hint.to_dict()}), 201


@bp.route("/<hint_id>", methods=["GET"])
def get_hint(hint_id: str):
    """Get a specific hint."""
    try:
        service = get_hints_service()
        hint = _run_async(service.get_hint_by_id(hint_id))
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to fetch user hint %s", hint_id)
        return _error(str(exc), 500)

    if hint is None:
        return _error(f"Hint not found: {hint_id}", 404)

    return jsonify({"ok": True, "hint": hint.to_dict()})


@bp.route("/<hint_id>/accept", methods=["POST"])
def accept_hint(hint_id: str):
    """Accept a hint suggestion and create the automation."""
    try:
        service = get_hints_service()
        success = _run_async(service.accept_suggestion(hint_id))
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to accept user hint %s", hint_id)
        return _error(str(exc), 500)

    if not success:
        return _error(f"Hint not found: {hint_id}", 404)

    return jsonify(
        {
            "ok": True,
            "message": "Suggestion accepted and automation created",
            "hint_id": hint_id,
        }
    )


@bp.route("/<hint_id>/reject", methods=["POST"])
def reject_hint(hint_id: str):
    """Reject a hint suggestion."""
    body, error_response = _optional_json_object()
    if error_response:
        return error_response

    reason, error_response = _parse_optional_string(body.get("reason"), field_name="reason")
    if error_response:
        return error_response

    try:
        service = get_hints_service()
        success = _run_async(service.reject_suggestion(hint_id, reason))
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to reject user hint %s", hint_id)
        return _error(str(exc), 500)

    if not success:
        return _error(f"Hint not found: {hint_id}", 404)

    return jsonify(
        {
            "ok": True,
            "message": "Suggestion rejected",
            "hint_id": hint_id,
        }
    )


@bp.route("/suggestions", methods=["GET"])
def list_suggestions():
    """List all suggestions."""
    try:
        service = get_hints_service()
        suggestions = service.get_suggestions()
    except Exception as exc:  # pragma: no cover - contract-tested via harness
        _LOGGER.exception("Failed to list user hint suggestions")
        return _error(str(exc), 500)

    return jsonify(
        {
            "ok": True,
            "suggestions": [suggestion.to_automation() for suggestion in suggestions],
            "count": len(suggestions),
        }
    )


@bp.route("/types", methods=["GET"])
def list_hint_types():
    """List available hint types."""
    return jsonify(
        {
            "ok": True,
            "types": [{"value": hint_type.value, "name": hint_type.name} for hint_type in HintType],
        }
    )
